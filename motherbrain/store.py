"""SQLite store for one or more shared brains.

One row space per brain_id. Every write carries agent_id (attribution);
recall is shared across all members of the brain. Short-term is scoped to
(agent_id, thread_id) unless the caller asks for shared=True.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS brains (
  id TEXT PRIMARY KEY, name TEXT, tier TEXT NOT NULL DEFAULT 'free',
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS members (
  brain_id TEXT NOT NULL, agent_id TEXT NOT NULL, kind TEXT, role TEXT,
  joined_at REAL NOT NULL, last_seen REAL, writes INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (brain_id, agent_id)
);
CREATE TABLE IF NOT EXISTS memories (
  id TEXT PRIMARY KEY, brain_id TEXT NOT NULL, agent_id TEXT NOT NULL,
  thread_id TEXT, stage TEXT NOT NULL, kind TEXT NOT NULL, scene TEXT,
  text TEXT NOT NULL, weight REAL NOT NULL DEFAULT 0.5, priority INTEGER NOT NULL DEFAULT 1,
  created_at REAL NOT NULL, expired INTEGER NOT NULL DEFAULT 0, dreamed INTEGER NOT NULL DEFAULT 0,
  meta TEXT
);
CREATE INDEX IF NOT EXISTS ix_mem_brain_stage ON memories(brain_id, stage, expired);
CREATE INDEX IF NOT EXISTS ix_mem_thread ON memories(brain_id, agent_id, thread_id);
CREATE TABLE IF NOT EXISTS lessons (
  id TEXT PRIMARY KEY, brain_id TEXT NOT NULL, agent_id TEXT NOT NULL,
  kind TEXT NOT NULL, trigger TEXT NOT NULL, consequence TEXT, rule TEXT NOT NULL,
  weight REAL NOT NULL, expires REAL, created_at REAL NOT NULL, hits INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mood (
  brain_id TEXT NOT NULL, field TEXT NOT NULL, value TEXT NOT NULL, updated_at REAL NOT NULL,
  PRIMARY KEY (brain_id, field)
);
CREATE TABLE IF NOT EXISTS refusals (
  id TEXT PRIMARY KEY, brain_id TEXT NOT NULL, agent_id TEXT, ts REAL NOT NULL,
  request_hash TEXT NOT NULL, trigger TEXT, category TEXT, model TEXT, outcome TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, brain_id TEXT NOT NULL, ts REAL NOT NULL,
  type TEXT NOT NULL, agent_id TEXT, payload TEXT
);
CREATE INDEX IF NOT EXISTS ix_events_brain ON events(brain_id, ts);
CREATE TABLE IF NOT EXISTS kv (
  k TEXT PRIMARY KEY, v TEXT NOT NULL, ts REAL NOT NULL
);
"""


def default_home() -> Path:
    return Path(os.environ.get("MB_HOME") or Path.home() / ".motherbrain")


def new_id() -> str:
    return uuid.uuid4().hex[:16]


class Store:
    def __init__(self, path: Optional[str] = None):
        if path is None:
            home = default_home()
            home.mkdir(parents=True, exist_ok=True)
            path = str(home / "brain.db")
        elif path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        if path != ":memory:":
            self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)

    # ---- low level -------------------------------------------------------
    def x(self, sql: str, args: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self.db.execute(sql, tuple(args))

    def rows(self, sql: str, args: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self.db.execute(sql, tuple(args)).fetchall()]

    def one(self, sql: str, args: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
        r = self.rows(sql, args)
        return r[0] if r else None

    # ---- brains / members -----------------------------------------------
    def ensure_brain(self, brain_id: str, tier: str, name: Optional[str] = None) -> Dict[str, Any]:
        b = self.one("SELECT * FROM brains WHERE id=?", [brain_id])
        if b is None:
            self.x("INSERT INTO brains(id,name,tier,created_at) VALUES(?,?,?,?)",
                   [brain_id, name or brain_id, tier, time.time()])
            b = self.one("SELECT * FROM brains WHERE id=?", [brain_id])
        elif b["tier"] != tier:
            self.x("UPDATE brains SET tier=? WHERE id=?", [tier, brain_id])
            b["tier"] = tier
        return b

    def upsert_member(self, brain_id: str, agent_id: str, kind: Optional[str], role: Optional[str]) -> bool:
        now = time.time()
        existed = self.one("SELECT 1 FROM members WHERE brain_id=? AND agent_id=?", [brain_id, agent_id])
        if existed:
            self.x("UPDATE members SET last_seen=?, kind=COALESCE(?,kind), role=COALESCE(?,role) "
                   "WHERE brain_id=? AND agent_id=?", [now, kind, role, brain_id, agent_id])
            return False
        self.x("INSERT INTO members(brain_id,agent_id,kind,role,joined_at,last_seen) VALUES(?,?,?,?,?,?)",
               [brain_id, agent_id, kind, role, now, now])
        return True

    def touch_member(self, brain_id: str, agent_id: str, wrote: bool = False) -> None:
        self.upsert_member(brain_id, agent_id, None, None)
        if wrote:
            self.x("UPDATE members SET writes=writes+1 WHERE brain_id=? AND agent_id=?", [brain_id, agent_id])

    def members(self, brain_id: str) -> List[Dict[str, Any]]:
        return self.rows("SELECT agent_id,kind,role,joined_at,last_seen,writes FROM members "
                         "WHERE brain_id=? ORDER BY joined_at", [brain_id])

    # ---- memories ---------------------------------------------------------
    def add_memory(self, **m: Any) -> str:
        mid = m.get("id") or new_id()
        self.x(
            "INSERT INTO memories(id,brain_id,agent_id,thread_id,stage,kind,scene,text,weight,priority,created_at,meta)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            [mid, m["brain_id"], m["agent_id"], m.get("thread_id"), m["stage"], m["kind"], m.get("scene"),
             m["text"], float(m.get("weight", 0.5)), int(m.get("priority", 1)),
             float(m.get("created_at") or time.time()), json.dumps(m.get("meta") or {})],
        )
        return mid

    def memories(self, brain_id: str, *, stages: Optional[List[str]] = None, agent_id: Optional[str] = None,
                 thread_id: Optional[str] = None, include_expired: bool = False, limit: int = 500,
                 since: Optional[float] = None, undreamed: bool = False) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM memories WHERE brain_id=?"
        args: List[Any] = [brain_id]
        if stages:
            sql += " AND stage IN (%s)" % ",".join("?" * len(stages))
            args += stages
        if agent_id is not None:
            sql += " AND agent_id=?"
            args.append(agent_id)
        if thread_id is not None:
            sql += " AND thread_id=?"
            args.append(thread_id)
        if not include_expired:
            sql += " AND expired=0"
        if since is not None:
            sql += " AND created_at>=?"
            args.append(since)
        if undreamed:
            sql += " AND dreamed=0"
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        out = self.rows(sql, args)
        for r in out:
            r["meta"] = json.loads(r["meta"] or "{}")
        return out

    def expire_short(self, brain_id: str, agent_id: str, thread_id: Optional[str], keep: int) -> int:
        ids = [r["id"] for r in self.rows(
            "SELECT id FROM memories WHERE brain_id=? AND agent_id=? AND IFNULL(thread_id,'')=IFNULL(?,'') "
            "AND stage='short' AND expired=0 ORDER BY created_at DESC LIMIT -1 OFFSET ?",
            [brain_id, agent_id, thread_id, keep])]
        for i in ids:
            self.x("UPDATE memories SET expired=1 WHERE id=?", [i])
        return len(ids)

    def mark_dreamed(self, ids: List[str]) -> None:
        for i in ids:
            self.x("UPDATE memories SET dreamed=1 WHERE id=?", [i])

    def expire(self, ids: List[str]) -> None:
        for i in ids:
            self.x("UPDATE memories SET expired=1 WHERE id=?", [i])

    # ---- lessons ----------------------------------------------------------
    def add_lesson(self, **l: Any) -> str:
        lid = new_id()
        self.x("INSERT INTO lessons(id,brain_id,agent_id,kind,trigger,consequence,rule,weight,expires,created_at)"
               " VALUES(?,?,?,?,?,?,?,?,?,?)",
               [lid, l["brain_id"], l["agent_id"], l["kind"], l["trigger"], l.get("consequence"), l["rule"],
                float(l["weight"]), l.get("expires"), time.time()])
        return lid

    def lessons(self, brain_id: str, include_expired: bool = False) -> List[Dict[str, Any]]:
        rows = self.rows("SELECT * FROM lessons WHERE brain_id=? ORDER BY weight DESC, created_at DESC", [brain_id])
        if include_expired:
            return rows
        now = time.time()
        return [r for r in rows if r["expires"] is None or r["expires"] > now]

    def hit_lesson(self, lesson_id: str) -> None:
        self.x("UPDATE lessons SET hits=hits+1 WHERE id=?", [lesson_id])

    # ---- mood -------------------------------------------------------------
    def mood(self, brain_id: str) -> Dict[str, Any]:
        return {r["field"]: json.loads(r["value"]) for r in
                self.rows("SELECT field,value FROM mood WHERE brain_id=?", [brain_id])}

    def set_mood(self, brain_id: str, values: Dict[str, Any]) -> None:
        now = time.time()
        for k, v in values.items():
            self.x("INSERT INTO mood(brain_id,field,value,updated_at) VALUES(?,?,?,?) "
                   "ON CONFLICT(brain_id,field) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                   [brain_id, k, json.dumps(v), now])

    # ---- refusals ---------------------------------------------------------
    def add_refusal(self, **r: Any) -> str:
        rid = new_id()
        self.x("INSERT INTO refusals(id,brain_id,agent_id,ts,request_hash,trigger,category,model,outcome)"
               " VALUES(?,?,?,?,?,?,?,?,?)",
               [rid, r["brain_id"], r.get("agent_id"), time.time(), r["request_hash"], r.get("trigger"),
                r.get("category"), r.get("model"), r.get("outcome", "declined")])
        return rid

    def refusals(self, brain_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        return self.rows("SELECT * FROM refusals WHERE brain_id=? ORDER BY ts DESC LIMIT ?", [brain_id, limit])

    # ---- events -----------------------------------------------------------
    def event(self, brain_id: str, type: str, agent_id: Optional[str] = None, **payload: Any) -> None:
        self.x("INSERT INTO events(brain_id,ts,type,agent_id,payload) VALUES(?,?,?,?,?)",
               [brain_id, time.time(), type, agent_id, json.dumps(payload, default=str)])

    def events(self, brain_id: str, limit: int = 200, types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM events WHERE brain_id=?"
        args: List[Any] = [brain_id]
        if types:
            sql += " AND type IN (%s)" % ",".join("?" * len(types))
            args += types
        sql += " ORDER BY ts DESC, id DESC LIMIT ?"
        args.append(limit)
        out = self.rows(sql, args)
        for e in out:
            e["payload"] = json.loads(e["payload"] or "{}")
        return out

    # ---- kv cache (JEV) ---------------------------------------------------
    def kv_get(self, k: str, max_age: Optional[float] = None) -> Optional[str]:
        r = self.one("SELECT v,ts FROM kv WHERE k=?", [k])
        if r is None or (max_age is not None and time.time() - r["ts"] > max_age):
            return None
        return r["v"]

    def kv_set(self, k: str, v: str) -> None:
        self.x("INSERT INTO kv(k,v,ts) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v, ts=excluded.ts",
               [k, v, time.time()])
