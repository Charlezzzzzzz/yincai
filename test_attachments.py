"""Local transport and persistence contracts for teacher attachments; no cloud model is called."""
import base64
from contextlib import closing
from io import BytesIO
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from uuid import uuid4
from zipfile import ZipFile

from PIL import Image, PngImagePlugin
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from chat_attachments import FORMATS, MAX_BODY
from chat_gateway import Provider
from serve import create_app
from test_chat import SyntheticUpstream, ThreadingHTTPServer
from test_review import request


def attachment(name, raw):
    return {"name":name, "mime":FORMATS[Path(name).suffix], "data":base64.b64encode(raw).decode("ascii")}


def pdf(text=None, pages=1):
    writer = PdfWriter()
    page = writer.add_blank_page(width=220, height=220)
    if text:
        font = DictionaryObject({NameObject("/Type"):NameObject("/Font"), NameObject("/Subtype"):NameObject("/Type1"),
                                 NameObject("/BaseFont"):NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):DictionaryObject({NameObject("/F1"):font})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    for _ in range(1,pages):
        writer.add_blank_page(width=220,height=220)
    output=BytesIO()
    writer.write(output)
    return output.getvalue()


def docx():
    buffer=BytesIO()
    with ZipFile(buffer, "w") as z:
        z.writestr("[Content_Types].xml",'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("word/document.xml",'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>逐项展开括号</w:t></w:r></w:p></w:body></w:document>')
    return buffer.getvalue()


def png():
    output=BytesIO()
    info=PngImagePlugin.PngInfo()
    info.add_text("Comment","local-source-marker")
    Image.new("RGB",(8,7),"#14213d").save(output, format="PNG", pnginfo=info)
    return output.getvalue()


class TeacherAttachments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1",0),SyntheticUpstream)
        cls.thread=Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def setUp(self):
        self.db=Path(self.enterContext(TemporaryDirectory()))/"review.sqlite3"
        self.key="unit-test-local-credential"
        self.provider=Provider(profile="custom",base=f"http://127.0.0.1:{self.server.server_port}/v1",
                               model="attachment-contract", credential=self.key)
        self.app=create_app(self.db,chat_provider=self.provider)
        self.server.calls=[]
        self.server.result=(200,{"choices":[{"message":{"content":"本轮测试意见"}}], "model":"attachment-contract"})

    def send(self, files, **extra):
        return request(self.app,"POST","/api/chat",{"role":"analyst","message":"请核对","attachments":files,**extra})

    def test_live_http_image_only_strips_metadata_and_never_replays_pixels(self):
        item=attachment("板书.png",png())
        status,receipt=self.send([item],message="")
        self.assertEqual(status,200,receipt)
        messages=self.server.calls[-1][1]["messages"]
        self.assertEqual([b["type"] for b in messages[-1]["content"]],["text","image_url"])
        mime,data=messages[-1]["content"][1]["image_url"]["url"].split(",",1)
        self.assertEqual(mime,"data:image/png;base64")
        clean=base64.b64decode(data)
        self.assertNotIn(b"local-source-marker",clean)
        with Image.open(BytesIO(clean)) as img:
            self.assertEqual(img.size,(8,7))
        self.assertEqual(receipt["attachments"][0]["kind"],"image")
        status,follow=self.send([],conversation_id=receipt["conversation_id"],message="追问")
        self.assertEqual(status,200,follow)
        self.assertNotIn("image_url",json.dumps(self.server.calls[-1][1]))
        with closing(sqlite3.connect(self.db)) as db:
            content=str(db.execute("SELECT * FROM agent_turns").fetchall())
            self.assertNotIn(item["data"],content)
            self.assertNotIn(data,content)
            self.assertNotIn(self.key,content)

    def test_echoed_credentials_and_encoded_attachment_never_enter_receipt(self):
        item = attachment("板书.png", png())
        self.server.result = (200, {"choices":[{"message":{"content":
            "附件引用 data:image/png;base64," + item["data"] + " 授权 " + self.key}}]})
        status, receipt = self.send([item], message="请核对：" + item["data"] + " " + self.key)
        self.assertEqual(status, 200, receipt)
        with closing(sqlite3.connect(self.db)) as db:
            stored = str(db.execute("SELECT question,input_text,receipt FROM agent_turns").fetchall())
        for sensitive in (item["data"], "data:image/png;base64,", self.key):
            self.assertNotIn(sensitive, stored)
            self.assertNotIn(sensitive, receipt["reply"])

    def test_text_documents_and_evidence_survive_reopen(self):
        docs=[attachment("备课.docx",docx()),attachment("课例.pdf",pdf("algebra exercise")),
              attachment("提示.md",("# 推理\n授权 "+self.key).encode())]
        code,result=self.send(docs)
        self.assertEqual(code,200,result)
        evidence=self.server.calls[-1][1]["messages"][-1]["content"]
        for value in ["逐项展开括号","algebra exercise","# 推理"]:
            self.assertIn(value,evidence)
        self.assertNotIn(self.key,evidence)
        self.app=create_app(self.db,chat_provider=self.provider)
        _,history=request(self.app,"GET","/api/chat/history/analyst/"+result["conversation_id"])
        self.assertEqual(len(history["turns"][0]["attachments"]),3)
        code,_=self.send([],conversation_id=result["conversation_id"])
        self.assertEqual(code,200)
        self.assertIn("algebra exercise",self.server.calls[-1][1]["messages"][1]["content"])
        with closing(sqlite3.connect(self.db)) as db:
            stored=str(db.execute("SELECT * FROM agent_turns").fetchall())
            self.assertNotIn(self.key,stored)
            self.assertTrue(all(x["data"] not in stored for x in docs))

    def test_handoff_transfers_only_model_reply(self):
        _,turn=self.send([attachment("策略.txt","不应自动转交的附件原文".encode())])
        code,result=self.send([],role="expert",handoff_from=turn["request_id"],message="核对上一岗位回复")
        self.assertEqual(code,200,result)
        body=self.server.calls[-1][1]["messages"][-1]["content"]
        self.assertIn("本轮测试意见",body)
        self.assertNotIn("不应自动转交",body)

    def test_receipt_idempotency_includes_exact_attachment_bytes(self):
        rid=str(uuid4())
        item=attachment("观察.csv","记录,人数\nA,8".encode())
        code,receipt=self.send([item],request_id=rid)
        self.assertEqual(code,200)
        self.assertFalse(receipt["replayed"])
        self.assertTrue(self.send([item],request_id=rid)[1]["replayed"])
        self.assertEqual(self.send([attachment("观察.csv",b"row,9")],request_id=rid)[0],409)
        self.assertEqual(len(self.server.calls),1)

    def test_unsupported_vision_does_not_write_or_fallback(self):
        self.server.result=(400,{"error":"upstream rejected image content"})
        status,body=self.send([attachment("板书.png",png())])
        self.assertEqual(status,502)
        self.assertIn("image_url",body["detail"])
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM agent_turns").fetchone()[0],0)
        self.assertEqual(len(self.server.calls),1)

    def test_rejects_invalid_types_sizes_and_textless_pdf_without_calling_upstream(self):
        text=attachment("notes.txt",b"notes")
        cases=[([text]*4,422),([{**text, "data":"%%%!"}],422),([{**text,"mime":"image/png"}],422),
               ([attachment("bad.jpg",b"not a picture")],422),([attachment("bad.docx",b"ordinary text")],422),
               ([attachment("legacy.txt",b"\xff")],422),([attachment("empty.pdf",pdf())],422),
               ([attachment("long.pdf",pdf(pages=31))],422),([attachment("long.csv",b"x"*12001)],422),
               ([attachment("bad.txt",b"%PDF-1.4 other")],422),([attachment("large.txt",b"x"*(MAX_BODY // 2))]*2,413)]
        for files,expected in cases:
            code,result=self.send(files)
            self.assertEqual(code,expected,result)
        self.assertFalse(self.server.calls)
