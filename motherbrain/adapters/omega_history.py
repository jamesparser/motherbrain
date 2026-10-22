"""Tail Omega's memory/history.metta into the shared brain.

Omega logs every step as  ("YYYY-MM-DD HH:MM:SS" (skill args...))  and incoming
messages as  ("ts" HUMAN_MESSAGE: ...). We turn that into:

  * `thought` events (what the agent is doing / noting / saying) for the owner's
    live "what is my AI thinking" panel, and
  * long-term memories for `pin` / `remember` (Omega's own notes-to-self), so the
    rest of the fleet can recall them.

Starts at the end of the file on first run (no backfill flood); keeps its byte
offset in the brain's kv table; handles truncation/rotation. Secrets are redacted.
"""
from __future__ import annotations

import os
import re
import time
from typing import Iterator, List, Optional, Tuple

from ..brain import Motherbrain
from ..refusal import redact

ENTRY = re.compile(r'^\("(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)"\s+(.*)\)\s*$', re.S)
SKILL = re.compile(r'^\(([a-zA-Z][\w-]*)\s*(.*)\)$', re.S)
SKIP = {"nop", "version", "update"}
NOTE_SKILLS = {"pin", "remember"}
MAX_TEXT = 400


def _unquote(args: str) -> str:
    a = args.strip()
    if a.startswith('"') and a.endswith('"') and len(a) >= 2:
        a = a[1:-1]
    return a.replace('\\"', '"').replace("\\n", " ").strip()


def parse(chunk: str) -> Iterator[Tuple[str, str, str]]:
    """Yield (ts, kind, text) for each complete entry in chunk."""
    buf: List[str] = []
    for line in chunk.splitlines():
        if line.startswith('("20') and buf:
            yield from _one("\n".join(buf))
            buf = []
        buf.append(line)
    if buf:
        yield from _one("\n".join(buf))


def _one(entry: str) -> Iterator[Tuple[str, str, str]]:
    m = ENTRY.match(entry.strip())
    if not m:
        return
    ts, body = m.group(1), m.group(2).strip()
    if body.startswith("HUMAN_MESSAGE:"):
        text = body[len("HUMAN_MESSAGE:"):].strip()
        text = re.sub(r"^\[\d+\]\s*\[[^\]]*\]\s*", "", text)
        yield ts, "message_in", text
        return
    s = SKILL.match(body)
    if not s:
        yield ts, "note", body
        return
    kind, args = s.group(1), s.group(2)
    if kind in SKIP:
        return
    yield ts, kind, _unquote(args)


class OmegaTail:
    def __init__(self, brain: Motherbrain, path: str, agent_id: str = "omega"):
        self.mb, self.path, self.agent = brain, path, agent_id
        self.key = f"omega_tail:{brain.brain_id}:{os.path.abspath(path)}"

    def _offset(self) -> Optional[int]:
        v = self.mb.store.kv_get(self.key)
        return int(v) if v else None

    def step(self) -> int:
        size = os.path.getsize(self.path)
        off = self._offset()
        if off is None or off > size:  # first run or file truncated/rotated: start at end
            self.mb.store.kv_set(self.key, str(size))
            return 0
        if off == size:
            return 0
        with open(self.path, "rb") as f:
            f.seek(off)
            data = f.read(min(size - off, 2_000_000))
        # only consume up to the last complete line
        cut = data.rfind(b"\n")
        if cut < 0:
            return 0
        data = data[: cut + 1]
        n = 0
        for ts, kind, text in parse(data.decode("utf-8", "replace")):
            text = redact(" ".join(text.split()))[:MAX_TEXT]
            if not text:
                continue
            self.mb.store.event(self.mb.brain_id, "thought", self.agent, kind=kind, text=text, at=ts)
            if kind in NOTE_SKILLS and len(text) > 20:
                try:
                    self.mb.write(text, agent_id=self.agent, stage="long", scene="working")
                except Exception:
                    pass
            n += 1
        self.mb.store.kv_set(self.key, str(off + len(data)))
        self.mb.store.touch_member(self.mb.brain_id, self.agent)
        return n

    def run(self, every: float = 5.0) -> None:
        while True:
            try:
                self.step()
            except FileNotFoundError:
                pass
            time.sleep(every)
