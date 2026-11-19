"""本机教师审阅服务。复用京师因材的缓存读取与学生端只读适配器。"""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
import uvicorn


WEB_ROOT = Path(__file__).resolve().parent
from app.case_files import ROOT as CASE_ROOT
from app.cockpit_comparison import build_cockpit_comparison
from app.teacher_case import bootstrap, microcourses, overview, verification_question

if sys.platform == "darwin":
    data_dir = Path.home() / "Library/Application Support/因才"
elif sys.platform == "win32":
    data_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "yincai"
else:
    data_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "yincai"
DEFAULT_DB = data_dir / "reviews.sqlite3"
DB_ID = 0x59433731
AVATARS = {f"avatars/{role}.webp" for role in ("analyst", "expert", "designer", "producer", "checker", "assistant")}

from agent_protocol import cache_events
from chat_attachments import ChatBodyLimit
from chat_gateway import chat_router, Provider
from student_alias import display_alias


class ReviewWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    student_id: str = Field(min_length=1, max_length=32)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_revision: int = Field(ge=0)
    action: Literal["pending", "modified", "adopted", "rejected"]
    current: str | None = Field(default=None, max_length=12000)


def prepare_db(path: Path) -> None:
    if path.suffix.lower() not in {".db", ".sqlite", ".sqlite3"} or path.is_relative_to(WEB_ROOT):
        raise ValueError("请选择独立的 v7 SQLite 文件，存于程序目录以外。")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
    except FileExistsError:
        pass
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        app_id = conn.execute("PRAGMA application_id").fetchone()[0]
        occupied = conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
        if app_id != DB_ID and (app_id != 0 or occupied):
            raise ValueError("指定的数据库已有其他应用的数据，请另选 v7 数据库。")
        conn.execute(f"PRAGMA application_id = {DB_ID}")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS private_reviews (
                student_id TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                original TEXT NOT NULL,
                current TEXT NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('pending','modified','adopted','rejected')),
                revision INTEGER NOT NULL CHECK(revision > 0),
                PRIMARY KEY (student_id, source_hash)
            )
        """)


def source_record(plan: dict) -> dict:
    meta = plan["model_meta"]
    if not meta or meta.get("source") != "cache" or not meta.get("input_hash"):
        raise HTTPException(503, "教师助理的建议来源尚未就绪。")
    original = plan["recommendation"]
    source = [meta["input_hash"], meta["prompt_version"], original, plan["teacher_summary"], plan["evidence"]]
    version = hashlib.sha256(json.dumps(source, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return {
        "student_id": plan["student_id"], "source_hash": version, "source_input_hash": meta["input_hash"],
        "original": original, "current": original, "action": "pending", "revision": 0,
    }


def read_records(connection: sqlite3.Connection, plans: list[dict]) -> list[dict]:
    records = []
    for plan in plans:
        if plan["status"] != "ready":
            continue
        record = display_alias(source_record(plan))
        row = connection.execute(
            "SELECT current, action, revision, original FROM private_reviews WHERE student_id=? AND source_hash=?",
            (record["student_id"], record["source_hash"]),
        ).fetchone()
        if row:
            record.update(current=record["original"] if row[0] == row[3] else row[0], action=row[1], revision=row[2])
        records.append(record)
    return records


def create_app(database: Path, web_root: Path = WEB_ROOT, *, chat_provider: Provider | None = None) -> FastAPI:
    database = database.expanduser().resolve()
    web_root = web_root.resolve()
    prepare_db(database)
    app = FastAPI(title="因才 · 教师本机审阅", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(chat_router(CASE_ROOT, chat_provider, database=database))
    app.add_middleware(ChatBodyLimit)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        if request.method not in {"GET", "HEAD"}:
            origin = request.headers.get("origin")
            expected = str(request.base_url).rstrip("/")
            if origin != expected or request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "教师写入仅限当前本机工作台。"}, status_code=403)
            if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
                return JSONResponse({"detail": "请以 JSON 提交工作台请求。"}, status_code=415)
        result = await call_next(request)
        result.headers["X-Content-Type-Options"] = "nosniff"
        result.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            result.headers["Cache-Control"] = "no-store"
        return result

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        if request.url.path.startswith("/api/chat/settings"):
            return JSONResponse({"detail": "请核对服务商、接口地址、模型和密钥字段。"}, status_code=422)
        if request.url.path == "/api/chat":
            if any("attachments" in error.get("loc", ()) for error in exc.errors()):
                return JSONResponse({"detail": "请提交最多 3 份附件，每份 3 MiB 以内，核对名称、类型和编码。"}, status_code=422)
            # Invalid browser input can contain arbitrary fields, including a pasted credential.
            # Never echo it or the raw validation payload in the response.
            return JSONResponse({"detail": "请使用有效角色，输入 1 至 2000 字的消息，并检查会话及请求编号。"}, status_code=422)
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(sqlite3.Error)
    async def storage_failed(_request, _error):
        return JSONResponse({"detail": "本地教师记录暂时无法读写，请保留草稿并重试。"}, status_code=503)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "yincai-v8.3.0", "teacher_only": True}

    app.add_api_route("/api/bootstrap", lambda: display_alias(bootstrap()), methods=["GET"])

    @app.get("/api/cockpit/comparison")
    def comparison_with_handoffs():
        data = build_cockpit_comparison()
        events = cache_events(data)
        return {**display_alias(data), "handoffs":events}
    @app.get("/api/verification")
    def verification(student_id: str = "S1"):
        try:
            return display_alias(verification_question(student_id))
        except ValueError as error:
            raise HTTPException(404, "未找到模拟学生。") from error

    @app.get("/api/microcourses")
    def available_microcourses():
        result = microcourses()
        for row in result["microcourses"]:
            pending = row["student_id"] == "S3"
            filename = f"microcourse-{row['student_id']}.mp4"
            available = not pending and (web_root / "media" / filename).is_file()
            row["availability"] = "pending_review" if pending else "available" if available else "missing_file"
            if not available:
                row["video_url"] = None
        return display_alias(result)

    def plan_overview():
        return overview()

    def snapshot(plans):
        with closing(sqlite3.connect(database)) as connection:
            connection.execute("BEGIN")
            return read_records(connection, plans)

    @app.get("/api/v7/reviews")
    def reviews():
        return {"reviews": snapshot(plan_overview()["plans"]), "teacher_only": True}

    @app.get("/api/teacher/overview")
    def teacher_overview():
        result = plan_overview()
        records = {r["student_id"]: r for r in snapshot(result["plans"])}
        result = display_alias(result)
        labels = {"pending": "待定", "modified": "已修改", "adopted": "已采纳", "rejected": "已否决"}
        for plan in result["plans"]:
            if review := records.get(plan["student_id"]):
                plan["private_review"] = review
                plan["decision_status"] = plan["display"]["状态"] = labels[review["action"]]
                plan["display"]["详情"]["下发说明"] = "本工作台的决定仅在教师端保存。"
        return result

    @app.get("/api/student/teacher-plan")
    def student_plan(student_id: str = "S1"):
        try:
            verification_question(student_id)
            return {"decision": None, "delivery_enabled": False, "scope": "本工作台只保存教师审阅，学生发布未开启。"}
        except ValueError as error:
            raise HTTPException(404, "未找到模拟学生。") from error

    @app.get("/api/student/learning-state")
    def learning_state(student_id: str = "S1"):
        try:
            verification_question(student_id)
            return {"reflection": None}
        except ValueError as error:
            raise HTTPException(404, "未找到模拟学生。") from error

    @app.post("/api/v7/reviews")
    def save(body: ReviewWrite):
        plans = plan_overview()["plans"]
        plan = next((p for p in plans if p["student_id"] == body.student_id), None)
        if not plan:
            raise HTTPException(404, "未找到模拟学生。")
        if plan["status"] != "ready":
            raise HTTPException(409, "该建议尚无可核对的缓存。")
        with closing(sqlite3.connect(database, timeout=5)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            review = read_records(conn, [plan])[0]
            if review["source_hash"] != body.source_hash or review["revision"] != body.expected_revision:
                raise HTTPException(409, "建议来源或记录版本已变化，请重新读取后核对草稿。")
            if body.action == "modified":
                if not body.current or not body.current.strip():
                    raise HTTPException(422, "修改后的建议不能为空。")
                review["current"] = body.current
            elif body.current is not None and body.current != review["current"]:
                raise HTTPException(422, "请先保存修改，再执行审阅决定。")
            if body.action == "pending":
                review["current"] = review["original"]
            review["action"] = body.action
            review["revision"] += 1
            conn.execute("""
                INSERT INTO private_reviews(student_id,source_hash,original,current,action,revision)
                VALUES(:student_id,:source_hash,:original,:current,:action,:revision)
                ON CONFLICT(student_id,source_hash) DO UPDATE SET
                    current=excluded.current, action=excluded.action, revision=excluded.revision
            """, review)
        return {"review": review, "teacher_only": True}

    @app.get("/microcourses/{filename}")
    @app.get("/media/{filename}")
    def media(filename: str):
        if filename not in {"microcourse-S1.mp4", "microcourse-S2.mp4"}:
            raise HTTPException(404)
        file = web_root / "media" / filename
        if not file.is_file():
            raise HTTPException(404)
        return FileResponse(file, media_type="video/mp4")

    @app.get("/")
    @app.get("/{asset:path}")
    def static_asset(asset: str = "index.html"):
        relative = Path(asset or "index.html")
        parts = relative.parts
        root_file = len(parts) == 1 and (relative.name == "index.html" or relative.suffix in {".css", ".js"})
        asset_file = len(parts) > 1 and parts[0] in {"assets", "models", "vendor", "fonts", "角色", "空间样张"} and relative.suffix.lower() in {
            ".png", ".jpg", ".jpeg", ".webp", ".svg", ".glb", ".gltf", ".bin", ".woff", ".woff2", ".js", ".css",
        }
        cover_file = len(parts) == 2 and parts[0] == "cover" and relative.suffix.lower() in {".webp", ".png", ".mp4"}
        candidate = (web_root / relative).resolve()
        if (not (root_file or asset_file or cover_file or asset in AVATARS) or any(p.startswith(".") for p in parts)
                or candidate != web_root / relative or not candidate.is_relative_to(web_root)
                or candidate == database or not candidate.is_file()):
            raise HTTPException(404)
        return FileResponse(candidate)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="启动因才本机教师工作台")
    parser.add_argument("--port", type=int, default=8772)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port 须为 1 至 65535 之间的整数。")
    with socket.socket() as server_socket:
        try:
            server_socket.bind(("127.0.0.1", args.port))
        except OSError as error:
            parser.exit(1, f"无法使用本机端口 {args.port}，可用 --port 指定其他端口。{error}\n")
        try:
            app = create_app(args.db)
        except (OSError, ValueError, sqlite3.Error) as error:
            parser.exit(1, f"无法打开独立教师数据库。{error}\n")
        print(f"因才工作台  http://127.0.0.1:{args.port}/\n教师记录  {args.db.expanduser().resolve()}\n按 Ctrl+C 停止。", flush=True)
        config = uvicorn.Config(app, host="127.0.0.1", port=args.port, proxy_headers=False, access_log=False)
        uvicorn.Server(config).run(sockets=[server_socket])


if __name__ == "__main__":
    main()
