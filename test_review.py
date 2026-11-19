"""本次服务使用临时数据库进行 ASGI 请求，无模型调用。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from serve import create_app


ORIGIN = "http://127.0.0.1:8767"


def request(app, method, path, body=None, *, origin=ORIGIN, query=b""):
    payload = json.dumps(body).encode() if body is not None else b""
    headers = [(b"host", b"127.0.0.1:8767"), (b"content-type", b"application/json")]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    scope = {
        "type": "http", "http_version": "1.1", "asgi": {"version": "3.0", "spec_version": "2.4"},
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": query, "headers": headers, "server": ("127.0.0.1", 8767),
        "client": ("127.0.0.1", 8080), "root_path": "",
    }

    async def perform():
        messages = []
        received = False

        async def receive():
            nonlocal received
            if received:
                await asyncio.Future()
            received = True
            return {"type": "http.request", "body": payload, "more_body": False}

        async def send(message):
            messages.append(message)

        await app(scope, receive, send)
        response = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
        start = next(m for m in messages if m["type"] == "http.response.start")
        media_type = dict(start["headers"]).get(b"content-type", b"").split(b";", 1)[0]
        return start["status"], json.loads(response) if media_type == b"application/json" else response

    return asyncio.run(perform())


class ReviewTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="yincai-v7-")
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.db = self.directory / "private.sqlite3"
        self.app = create_app(self.db, self.directory)
        self.initial = self.get()[0]

    def get(self):
        code, result = request(self.app, "GET", "/api/v7/reviews")
        self.assertEqual(code, 200)
        self.assertIs(result["teacher_only"], True)
        return result["reviews"]

    def change(self, record, action, **more):
        payload = {"student_id": record["student_id"], "source_hash": record["source_hash"],
                   "expected_revision": record["revision"], "action": action, **more}
        return request(self.app, "POST", "/api/v7/reviews", payload)

    def test_review_persists_across_reopen_and_never_enters_student_projection(self):
        self.assertEqual([(r["student_id"], r["action"]) for r in self.get()],
                         [("S1", "pending"), ("S2", "pending"), ("S3", "pending")])
        original = self.initial["original"]
        code, result = self.change(self.initial, "modified", current="教师私有的新建议。")
        self.assertEqual(code, 200)
        modified = result["review"]
        self.assertEqual((modified["current"], modified["action"], modified["revision"]),
                         ("教师私有的新建议。", "modified", 1))
        self.app = create_app(self.db, self.directory)
        self.assertEqual(self.get()[0], modified)
        for action, revision in [("adopted", 2), ("rejected", 3), ("pending", 4)]:
            code, result = self.change(modified, action)
            self.assertEqual(code, 200)
            modified = result["review"]
            self.assertEqual((modified["action"], modified["revision"]), (action, revision))
            self.assertEqual(modified["original"], original)
            self.assertEqual(modified["current"], original if action == "pending" else "教师私有的新建议。")
            self.assertEqual(self.get()[0], modified)
            code, public = request(self.app, "GET", "/api/student/teacher-plan", query=b"student_id=S1")
            self.assertEqual(code, 200)
            self.assertIsNone(public["decision"])
            self.assertIs(public["delivery_enabled"], False)

    def test_concurrent_requests_accept_only_one_revision(self):
        def submit(text):
            return self.change(self.initial, "modified", current=text)[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(submit, ["甲方案", "乙方案"])), [200, 409])
        latest = self.get()[0]
        self.assertIn(latest["current"], {"甲方案", "乙方案"})
        self.assertEqual(latest["revision"], 1)

    def test_teacher_text_preserves_quoted_names(self):
        text = "请比较小安与小川。"
        status, _ = self.change(self.initial, "modified", current=text)
        self.assertEqual(status, 200)
        self.assertEqual(self.get()[0]["current"], text)
        status, overview = request(self.app, "GET", "/api/teacher/overview")
        self.assertEqual(status, 200)
        plan = next(p for p in overview["plans"] if p["student_id"] == self.initial["student_id"])
        self.assertEqual(plan["private_review"]["current"], text)

    def test_writes_validate_origin_source_and_request(self):
        payload = {"student_id": "S1", "source_hash": self.initial["source_hash"],
                   "expected_revision": 0, "action": "adopted"}
        for origin in [None, "null", "http://localhost:3000"]:
            self.assertEqual(request(self.app, "POST", "/api/v7/reviews", payload, origin=origin)[0], 403)
        for fields, expected in [
            ({"source_hash": "a" * 64}, 409), ({"action": "modified", "current": " "}, 422),
            ({"action": "release"}, 422), ({"student_id": "S99"}, 404),
            ({"action": "adopted", "current": "未经单独保存"}, 422),
            ({"student_message": "不属于教师私有审阅"}, 422),
        ]:
            self.assertEqual(request(self.app, "POST", "/api/v7/reviews", {**payload, **fields})[0], expected)
        self.assertEqual(self.initial, self.get()[0])

    def test_reuses_real_cached_data_and_blocks_legacy_writes_and_private_files(self):
        code, comparison = request(self.app, "GET", "/api/cockpit/comparison")
        self.assertEqual(code, 200)
        self.assertEqual(comparison["display"]["总耗时"]["秒"], 526.813)
        code, boot = request(self.app, "GET", "/api/bootstrap")
        self.assertEqual(code, 200)
        self.assertEqual(boot["classroom"]["classroom"]["student_count"], 30)
        self.assertEqual(boot["classroom"]["classroom"]["top_three_count"], 23)
        code, proposal = request(self.app, "GET", "/api/teacher/overview")
        self.assertEqual(code, 200)
        self.assertEqual(proposal["plans"][0]["recommendation"], self.initial["original"])
        self.assertEqual(proposal["plans"][0]["private_review"], self.initial)
        for path in ["/api/verification", "/api/microcourses", "/api/student/learning-state"]:
            self.assertEqual(request(self.app, "GET", path)[0], 200)
        for method, path in [
            ("GET", "/api/demo/stream"), ("GET", "/api/photo/diagnose"), ("POST", "/api/teacher/decisions"),
            ("POST", "/api/verification"), ("POST", "/api/microcourses/regenerate"),
            ("GET", "/serve.py"), ("GET", "/private.sqlite3"),
        ]:
            self.assertIn(request(self.app, method, path)[0], {404, 405})

    def test_root_serves_the_same_workbench_as_the_explicit_index(self):
        page = b"<!doctype html><title>Yincai</title>"
        (self.directory / "index.html").write_bytes(page)
        for path in ["/", "/index.html"]:
            self.assertEqual(request(self.app, "GET", path), (200, page))

    def test_refuses_an_unrelated_existing_database(self):
        other = self.directory / "other.db"
        with sqlite3.connect(other) as conn:
            conn.execute("CREATE TABLE unrelated(value TEXT)")
        with self.assertRaisesRegex(ValueError, "其他应用"):
            create_app(other, self.directory)
        with sqlite3.connect(other) as conn:
            self.assertEqual(conn.execute("SELECT name FROM sqlite_master").fetchall(), [("unrelated",)])


if __name__ == "__main__":
    unittest.main()
