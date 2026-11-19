"""Bounded text extraction for teacher-supplied Office and PDF documents."""
from io import BytesIO
import json
import os
import subprocess
import sys
import zlib
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile

from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException

MAX_TEXT = 12_000
MAX_FILE = 3 * 1024 * 1024
WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CONTENT_TYPE = "{http://schemas.openxmlformats.org/package/2006/content-types}Override"


class DocumentError(ValueError):
    pass


def checked_text(value):
    value = value.strip()
    if len(value) > MAX_TEXT:
        raise DocumentError("每份附件正文最多 12000 个字符，请缩短或拆分后另行发送。")
    if not value:
        raise DocumentError("没有可提取的文字。扫描件请改传为图片并选择支持视觉的模型。")
    return value


def docx_text(data):
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            if len(entries) > 256 or len(names) != len(entries) or sum(e.file_size for e in entries) > 16 * 1024 * 1024:
                raise DocumentError("DOCX 内部文件过多或解压后过大，请精简文件。")
            if any(e.flag_bits & 1 or e.compress_type not in {ZIP_DEFLATED, ZIP_STORED} for e in entries):
                raise DocumentError("不支持加密或使用特殊压缩方式的 DOCX。")
            def xml_member(name, limit):
                with archive.open(name) as stream:
                    raw = stream.read(limit + 1)
                if len(raw) > limit:
                    raise DocumentError("DOCX 正文或索引过大，请精简文件。")
                return fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
            types = xml_member("[Content_Types].xml", 100_000)
            if not any(r.get("PartName") == "/word/document.xml" and
                       r.get("ContentType") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
                       for r in types.findall(CONTENT_TYPE)):
                raise DocumentError("该文件不是标准 DOCX 文档。")
            root = xml_member("word/document.xml", MAX_FILE)
    except (BadZipFile, KeyError, OSError, RuntimeError, EOFError, zlib.error, ParseError, DefusedXmlException) as exc:
        raise DocumentError("无法读取 DOCX，请使用未加密的标准 Word 文档。") from exc
    if root.tag != WORD + "document":
        raise DocumentError("DOCX 缺少有效正文。")
    parts = {WORD + "p":"\n", WORD + "br":"\n", WORD + "cr":"\n", WORD + "tab":"\t"}
    return checked_text("".join((node.text or "") if node.tag == WORD + "t" else parts.get(node.tag, "")
                                for node in root.iter()))


def pdf_text(data):
    """The worker limits PDF parsing time and stream expansion; it writes no files."""
    if not data.startswith(b"%PDF-"):
        raise DocumentError("文件内容与 PDF 类型不符。")
    try:
        proc = subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).resolve()), "pdf"],
                              input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10,
                              env={k:v for k,v in os.environ.items() if k in {"SYSTEMROOT", "WINDIR", "LANG", "PATH"}})
        obj = json.loads(proc.stdout) if proc.returncode == 0 else {}
    except (ValueError, subprocess.TimeoutExpired, OSError):
        obj = {}
    if "text" not in obj:
        raise DocumentError(obj.get("error", "PDF 过于复杂或损坏，请另存为较小的文本 PDF。"))
    return obj["text"]


def read_pdf_worker(data):
    try:
        import resource
        for limit, value in [(resource.RLIMIT_CPU, 7), (resource.RLIMIT_DATA, 512 * 1024 * 1024)]:
            try:
                _, hard = resource.getrlimit(limit)
                resource.setrlimit(limit, (value if hard == resource.RLIM_INFINITY else min(value, hard), hard))
            except (OSError, ValueError):
                pass
    except ImportError:
        pass
    from pypdf import PdfReader, filters
    for key in ("ZLIB_MAX_OUTPUT_LENGTH", "RUN_LENGTH_MAX_OUTPUT_LENGTH", "LZW_MAX_OUTPUT_LENGTH",
                "MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH", "MAX_DECLARED_STREAM_LENGTH", "JBIG2_MAX_OUTPUT_LENGTH"):
        setattr(filters, key, 8 * 1024 * 1024)
    reader = PdfReader(BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise DocumentError("请先解除 PDF 加密，再作为附件发送。")
    if len(reader.pages) > 30:
        raise DocumentError("每份 PDF 最多 30 页，请选取需要分析的页面。")
    pieces = []
    for page in reader.pages:
        pieces.append(page.extract_text() or "")
        if sum(map(len, pieces)) > MAX_TEXT:
            raise DocumentError("每份附件正文最多 12000 个字符，请缩短后发送。")
    return checked_text("\n".join(pieces))


if __name__ == "__main__":
    try:
        data = sys.stdin.buffer.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise DocumentError("单个附件超过 3 MiB。")
        result = {"text": read_pdf_worker(data)}
    except DocumentError as exc:
        result = {"error": str(exc)}
    except Exception:
        result = {"error": "此 PDF 无法安全提取文字，请另存为文本 PDF 或上传图片。"}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=True).encode("ascii"))
