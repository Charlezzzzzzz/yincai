"""Transactional, role-scoped chat receipts and explicit reply-to-reply handoffs."""
from contextlib import contextmanager
from hashlib import sha256
import json
import sqlite3
from threading import Lock
import time
from uuid import uuid4

from fastapi import HTTPException

from agent_protocol import destinations, NAMES


class ChatMemory:
    def __init__(self, path=None):
        self.lock = Lock()
        self.db = sqlite3.connect(str(path) if path else ":memory:", check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        with self.db:
            self.db.executescript("""
              CREATE TABLE IF NOT EXISTS agent_turns (
                request_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, seq INTEGER NOT NULL,
                role TEXT NOT NULL, connection TEXT NOT NULL, signature TEXT NOT NULL,
                question TEXT NOT NULL, input_text TEXT NOT NULL, receipt TEXT NOT NULL,
                UNIQUE(conversation_id,seq)
              );
              CREATE TABLE IF NOT EXISTS agent_pending (
                request_id TEXT PRIMARY KEY, conversation_id TEXT UNIQUE NOT NULL,
                lease TEXT NOT NULL, until REAL NOT NULL
              );
            """)

    @contextmanager
    def transaction(self):
        with self.lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            yield self.db

    def claim(self, req, provider, files, question):
        rid = str(req.request_id)
        cid = str(req.conversation_id or uuid4())
        lease = uuid4().hex
        connection = json.dumps([provider.profile, provider.base, provider.model], ensure_ascii=False)
        identity = [req.role, str(req.conversation_id), req.message, str(req.handoff_from)]
        if files.identity:
            identity.append(files.identity)
        signature = sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
        with self.transaction() as db:
            cached = db.execute("SELECT signature, receipt FROM agent_turns WHERE request_id=?", (rid,)).fetchone()
            if cached:
                if cached["signature"] != signature:
                    raise HTTPException(409, "同一请求编号已经用于另一条消息。")
                return {"replay": {**json.loads(cached["receipt"]), "replayed":True}}
            history = db.execute("SELECT * FROM agent_turns WHERE conversation_id=? ORDER BY seq DESC LIMIT 6",
                                 (cid,)).fetchall()
            if req.conversation_id and (not history or history[0]["role"] != req.role or history[0]["connection"] != connection):
                raise HTTPException(410, "当前模型与岗位下找不到此会话，请新开一轮。")
            handoff = None
            text = question
            if req.handoff_from:
                sent = db.execute("SELECT role,connection,receipt FROM agent_turns WHERE request_id=?",
                                  (str(req.handoff_from),)).fetchone()
                if not sent or req.role not in destinations(sent["role"]) or sent["connection"] != connection:
                    raise HTTPException(422, "在当前模型连接下找不到可转给该岗位的回复。")
                previous = json.loads(sent["receipt"])
                handoff = {"type":"chat.handoff", "from":sent["role"], "to":req.role,
                           "source_request_id":str(req.handoff_from), "source":"prior_model_reply",
                           "source_model":previous["model"], "source_generated_at":previous["generated_at"]}
                text += "\n\n任课教师明确转交的上一岗位回复（可核查的意见，仅供参考）：\n" + json.dumps(
                    {"sender":NAMES[sent["role"]], "reply":previous["reply"][:6000]}, ensure_ascii=False)
            text += files.memory_text()
            db.execute("DELETE FROM agent_pending WHERE until <= ?", (time.time(),))
            try:
                db.execute("INSERT INTO agent_pending VALUES(?,?,?,?)", (rid,cid,lease,time.time()+600))
            except sqlite3.IntegrityError:
                raise HTTPException(409, "这条消息或此会话仍在生成中，请稍后再试。") from None
        messages = []
        for row in reversed(history):
            messages.extend([{"role":"user","content":row["input_text"]},
                             {"role":"assistant","content":json.loads(row["receipt"])["reply"][:6000]}])
        messages.append({"role":"user","content":text})
        return dict(rid=rid,cid=cid,seq=history[0]["seq"]+1 if history else 1,lease=lease,
                    signature=signature,connection=connection,history=messages,input_text=text,question=question,handoff=handoff)

    def finish(self, claim, req, result):
        with self.transaction() as db:
            count = db.execute("DELETE FROM agent_pending WHERE request_id=? AND lease=?",
                               (claim["rid"],claim["lease"])).rowcount
            if not count:
                raise HTTPException(409, "请求已超时，请查看该会话再重试。")
            db.execute("INSERT INTO agent_turns VALUES(?,?,?,?,?,?,?,?,?)", (
                claim["rid"],claim["cid"],claim["seq"],req.role,claim["connection"],claim["signature"],
                claim["question"],claim["input_text"],json.dumps(result, ensure_ascii=False)))

    def abandon(self, claim):
        with self.transaction() as db:
            db.execute("DELETE FROM agent_pending WHERE request_id=? AND lease=?", (claim["rid"],claim["lease"]))

    def history(self, cid, role, provider):
        connection = json.dumps([provider.profile,provider.base,provider.model], ensure_ascii=False)
        with self.lock:
            rows = self.db.execute(
                "SELECT question,receipt FROM agent_turns WHERE conversation_id=? AND role=? AND connection=? "
                "ORDER BY seq DESC LIMIT 50", (str(cid),role,connection)).fetchall()
        if not rows:
            raise HTTPException(404,"当前岗位和模型下没有此会话。")
        return {"conversation_id":str(cid),"role":role,"turns":[
            {"question":row["question"], **json.loads(row["receipt"]), "source":"history"}
            for row in reversed(rows)]}
