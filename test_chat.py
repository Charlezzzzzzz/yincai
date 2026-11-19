"""Role chat transport contract with an explicitly synthetic loopback provider. No secrets or paid calls."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

from serve import create_app, CASE_ROOT
from chat_gateway import ChatInput, ChatService, Provider
from test_review import request


class SyntheticUpstream(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.calls.append((self.path,body))
        result = self.server.result
        self.send_response(result[0]);self.send_header("Content-Type","application/json");self.end_headers()
        self.wfile.write(json.dumps(result[1]).encode())


class LiveRouteContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1",0),SyntheticUpstream)
        cls.runner = threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.runner.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.runner.join()

    def setUp(self):
        stack = self.enterContext(ExitStack())
        db = Path(stack.enter_context(TemporaryDirectory()))/"isolated.sqlite3"
        stack.enter_context(patch.dict("os.environ",{
            "YINCAI_CHAT_BASE_URL":f"http://127.0.0.1:{self.server.server_port}/v1",
            "YINCAI_CHAT_MODEL":"synthetic-contract-model","YINCAI_CHAT_API_KEY":""}))
        self.provider = Provider()
        self.app = create_app(db,chat_provider=self.provider)
        self.server.calls = []
        self.server.result = (200,{"choices":[{"message":{"role":"assistant","content":"仅用于传输测试的上游回答"}}],
                                  "model":"synthetic-contract-model"})

    def chat(self, **params):
        return request(self.app,"POST","/api/chat",{"role":"analyst","message":"这是一条传输测试",**params})

    def test_multiturn_uses_real_http_and_server_roles(self):
        status, cfg = request(self.app,"GET","/api/chat/status")
        self.assertEqual((status,cfg["configured"],cfg["provider"]),(200,True,"compatible"))
        status, one = self.chat()
        self.assertEqual((status,one["source"],one["role"],one["replayed"]),(200,"live","analyst",False))
        self.assertEqual(one["reply"],self.server.result[1]["choices"][0]["message"]["content"])
        status,two = self.chat(message="跟进上下文",conversation_id=one["conversation_id"])
        self.assertEqual((status,two["conversation_id"]),(200,one["conversation_id"]))
        path,body = self.server.calls[-1]
        self.assertEqual((path,body["model"],body["stream"]),("/v1/chat/completions","synthetic-contract-model",False))
        turns = body["messages"]
        self.assertEqual([m["role"] for m in turns],["system","user","assistant","user"])
        self.assertEqual(turns[2]["content"],one["reply"])
        for evidence in ["学情分析师","526.8","解为13","23名不同学生","01"]:
            self.assertIn(evidence,turns[0]["content"])
        self.assertEqual(self.chat(role="checker",conversation_id=one["conversation_id"])[0],410)
        self.assertEqual(len(self.server.calls),2)
        for role in ("expert","designer","producer","checker","assistant"):
            self.assertEqual(self.chat(role=role)[0],200)
            self.assertEqual(len(self.server.calls[-1][1]["messages"]),2)

    def test_http_errors_empty_data_and_invalid_requests_never_look_live(self):
        for malformed in [None, {}, {"choices":[]}, {"choices":[{"message":{"content":"  "}}]}]:
            self.server.result=(200,malformed)
            code,res=self.chat()
            self.assertEqual(code,502);self.assertNotIn("source",res)
        self.server.result=(401,{"error":"PRIVATE UPSTREAM DEBUG"})
        code,res=self.chat()
        self.assertEqual(code,502);self.assertNotIn("PRIVATE",str(res))
        prior=len(self.server.calls)
        for fields in [{"role":"system"},{"message":" "},{"message":"长"*2001},{"messages":[]},{"api_key":"blocked"},
                       {"base_url":"http://localhost"},{ "conversation_id":"invalid"}]:
            self.assertEqual(self.chat(**fields)[0],422)
        self.assertEqual(request(self.app,"POST","/api/chat",{"role":"expert","message":"x"},origin="http://other.invalid")[0],403)
        self.assertEqual(len(self.server.calls),prior)

    def test_receipt_replay_does_not_make_another_call(self):
        rid=str(uuid4());code,first=self.chat(request_id=rid)
        self.assertEqual(code,200)
        code,duplicate=self.chat(request_id=rid)
        self.assertTrue(duplicate["replayed"]);self.assertEqual(duplicate["generated_at"],first["generated_at"])
        self.assertEqual(self.chat(request_id=rid,message="不同消息")[0],409)
        self.assertEqual(len(self.server.calls),1)

    def test_failed_requests_do_not_change_chat_history(self):
        _,first=self.chat()
        self.server.result=(503,{})
        self.assertEqual(self.chat(conversation_id=first["conversation_id"],message="中途失败")[0],502)
        self.server.result=(200,{"choices":[{"message":{"content":"下一次成功"}}]})
        self.assertEqual(self.chat(conversation_id=first["conversation_id"],message="重试问题")[0],200)
        self.assertNotIn("中途失败",str(self.server.calls[-1][1]["messages"]))

    def test_parallel_call_in_same_thread_is_not_issued_twice(self):
        service=ChatService(CASE_ROOT,self.provider)
        first=service.send(ChatInput(role="assistant",message="first"))
        follow=ChatInput(role="assistant",message="later",conversation_id=first["conversation_id"])
        entered=threading.Event();release=threading.Event()
        def wait_for_model(messages):
            entered.set();release.wait(3);return "finished","local-test"
        with patch.object(self.provider,"complete",side_effect=wait_for_model),ThreadPoolExecutor(max_workers=2) as pool:
            job=pool.submit(service.send,follow);self.assertTrue(entered.wait(2))
            try:
                with self.assertRaises(Exception) as collision:service.send(follow)
                self.assertEqual(collision.exception.status_code,409)
            finally:release.set()
            self.assertEqual(job.result()["reply"],"finished")

    def test_remote_requires_https_and_server_config(self):
        for base,model in (("http://api.example.test/v1","a"),("https://api.example.test/v1",""),
                           ("https://api.example.test/v1","a"),("https://user:pass@example.test/v1","a")):
            with patch.dict("os.environ",{"YINCAI_CHAT_BASE_URL":base,"YINCAI_CHAT_MODEL":model,"YINCAI_CHAT_API_KEY":""}):
                provider=Provider()
                self.assertFalse(provider.status()["configured"])
                with self.assertRaises(Exception) as err:provider.complete([])
                self.assertEqual(err.exception.status_code,503)


if __name__ == "__main__":
    unittest.main()
