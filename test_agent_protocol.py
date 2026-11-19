"""Exercises actual API routes against isolated storage and an instrumented test model."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from serve import create_app
from chat_gateway import Provider
from test_review import request


class ProtocolAndMemory(TestCase):
    def setUp(self):
        self.db = Path(self.enterContext(TemporaryDirectory())) / "case.sqlite3"
        self.provider = Provider(profile="ollama",base="http://localhost:11434",model="contract-fixture")
        self.upstream = self.enterContext(patch.object(self.provider,"complete",
            return_value=("上游测试回执","contract-fixture")))
        self.app = self.open_app()

    def open_app(self):
        return create_app(self.db,chat_provider=self.provider)

    def send(self,role,message,app=None,**kwargs):
        return request(app or self.app,"POST","/api/chat",dict(role=role,message=message,**kwargs))

    def test_case_handoffs_use_real_file_provenance(self):
        status,data=request(self.app,"GET","/api/cockpit/comparison")
        self.assertEqual(status,200)
        events=data["handoffs"]
        self.assertEqual(len(events),8)
        for i,event in enumerate(events):
            self.assertEqual(event["seq"],i+1)
            self.assertEqual(event["source"],"cache")
            self.assertEqual(event["file_sha256"],data["display"]["步骤详情"][f"{i+1:02d}"]["文件哈希"])
            self.assertEqual(event["event_id"], f"cache:{i+1:02d}:{event['archived_file_sha256']}")
            if i:
                self.assertEqual(event["previous_event_id"],events[i-1]["event_id"])
                self.assertEqual(event["sender"],events[i-1]["recipient"])
        self.assertEqual(events[4]["recipient"],"producer")
        self.assertEqual(events[-1]["recipient"],"teacher")
        self.assertEqual(round(data["protocol"]["cache_round_elapsed_seconds"],1),526.8)

    def test_handoff_separates_private_chat_and_recipient_model_run(self):
        self.upstream.return_value=("转交给专家的诊断反馈","contract-fixture")
        _,one=self.send("analyst","私聊原句不能跨角色")
        self.upstream.return_value=("专家根据诊断给出的独立建议","contract-fixture")
        status,two=self.send("expert","请复核",handoff_from=one["request_id"])
        self.assertEqual(status,200)
        self.assertEqual(two["handoff"]["from"],"analyst")
        self.assertEqual(two["source"],"live")
        reached=self.upstream.call_args.args[0][-1]["content"]
        self.assertIn("转交给专家的诊断反馈",reached)
        self.assertNotIn("私聊原句不能跨角色",reached)
        self.assertEqual(self.send("assistant","跳过岗位",handoff_from=one["request_id"])[0],422)
        self.assertEqual(self.upstream.call_count,2)

    def test_reopen_history_replay_and_scope(self):
        rid=str(uuid4())
        _,one=self.send("checker","查初稿",request_id=rid)
        restarted=self.open_app()
        _,duplicate=self.send("checker","查初稿",app=restarted,request_id=rid)
        self.assertTrue(duplicate["replayed"])
        self.assertEqual(self.upstream.call_count,1)
        self.assertEqual(self.send("checker","改写请求",app=restarted,request_id=rid)[0],409)
        cid=one["conversation_id"]
        code,later=self.send("checker","继续",app=restarted,conversation_id=cid)
        self.assertEqual((code,later["seq"]),(200,2))
        self.assertIn("查初稿",str(self.upstream.call_args.args[0][1:]))
        self.assertEqual(self.send("expert","旁观",app=restarted,conversation_id=cid)[0],410)
        status, history=request(restarted,"GET",f"/api/chat/history/checker/{cid}")
        self.assertEqual((status,len(history["turns"])),(200,2))
        self.assertTrue(all(t["source"]=="history" for t in history["turns"]))
        self.assertEqual(request(restarted,"GET",f"/api/chat/history/expert/{cid}")[0],404)
        with patch.object(self.provider,"model","different-model"):
            self.assertEqual(self.send("checker","不可外传",conversation_id=cid)[0],410)
            self.assertEqual(self.send("producer","跨模型",handoff_from=rid)[0],422)

    def test_shared_db_reserves_before_calling_upstream(self):
        _,one=self.send("expert","开始")
        second_app=self.open_app()
        started,release=Event(),Event()
        def wait_for_provider(_):
            started.set(); release.wait(5); return "完成","contract-fixture"
        self.upstream.side_effect=wait_for_provider
        with ThreadPoolExecutor(max_workers=1) as pool:
            task=pool.submit(self.send,"expert","正在生成",conversation_id=one["conversation_id"])
            self.assertTrue(started.wait(2))
            try:
                self.assertEqual(self.send("expert","同时发起",app=second_app,conversation_id=one["conversation_id"])[0],409)
            finally:
                release.set()
            self.assertEqual(task.result()[0],200)
