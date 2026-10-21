"""Soul file: motherbrain.md.

Rewritten after every mood / lesson / evolve write. Agents are told to
`RE-READ motherbrain.md` (or call mb_reload) so changes apply without reboot.
Optionally mirrored into an AGENTS.md block between markers.
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import mood as moodlib

START = "<!-- motherbrain:start -->"
END = "<!-- motherbrain:end -->"
RELOAD_PROMPT = "RE-READ motherbrain.md"


def render(brain: Dict[str, Any], members: List[Dict[str, Any]], mood: Dict[str, Any],
           lessons: List[Dict[str, Any]], identity: List[Dict[str, Any]], dream: Optional[str]) -> str:
    m = moodlib.merged(mood)
    lines = [
        f"# Motherbrain — {brain.get('name') or brain['id']}",
        "",
        f"_Shared brain · tier {brain.get('tier', 'free')} · updated {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}_",
        "",
        "You are one of several agents sharing this brain. What any member learns, all members know.",
        "Recall with `mb_search`; record hard lessons with `mb_lesson`. When told "
        f"`{RELOAD_PROMPT}`, re-read this file before your next step.",
        "",
        "## Members",
    ]
    lines += [f"- `{x['agent_id']}`" + (f" ({x['kind']})" if x.get("kind") else "") +
              (f" — {x['role']}" if x.get("role") else "") for x in members] or ["- (none yet)"]
    lines += ["", f"## Tone (mood: {m.get('mood_bias', 'neutral')})",
              "_Tone only. Mood never blocks tools or legitimate work._", ""]
    tl = moodlib.tone_lines(m)
    lines += [f"- {t}" for t in tl] or ["- Even, helpful, plain."]
    hard = [l for l in lessons if l["kind"] in ("trauma", "hard_lesson")]
    soft = [l for l in lessons if l["kind"] not in ("trauma", "hard_lesson")]
    if hard:
        lines += ["", "## Hard lessons (check before planning)"]
        for l in hard[:12]:
            lines.append(f"- **When** {l['trigger']} → {l['rule']}"
                         + (f" _(last time: {l['consequence']})_" if l.get("consequence") else "")
                         + f" · from `{l['agent_id']}`")
    if soft:
        lines += ["", "## Wins & boundaries"]
        for l in soft[:12]:
            tag = "win" if l["kind"] == "win" else "boundary"
            lines.append(f"- [{tag}] {l['trigger']} → {l['rule']}")
    if identity:
        lines += ["", "## Long-term identity"]
        lines += [f"- {i['text']}" for i in identity[:12]]
    if dream:
        lines += ["", "## Last dream", dream]
    lines += ["", "---", f"_{RELOAD_PROMPT} after any change. No reboot needed._", ""]
    return "\n".join(lines)


class Soul:
    def __init__(self, path: Path, agents_md: Optional[Path] = None):
        self.path = Path(path)
        self.agents_md = Path(agents_md) if agents_md else None
        self._listeners: List[Callable[[str, str], None]] = []
        self.version = 0
        self.hash = ""

    def on_change(self, fn: Callable[[str, str], None]) -> None:
        """Harness hook: notify_soul_changed(path, hash) -> pull file next turn."""
        self._listeners.append(fn)

    def write(self, text: str) -> Dict[str, Any]:
        h = hashlib.sha256(text.split("\n", 3)[-1].encode()).hexdigest()[:12]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".md.tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.path)
        if self.agents_md:
            self._mirror(text)
        changed = h != self.hash
        self.hash = h
        if changed:
            self.version += 1
            for fn in self._listeners:
                try:
                    fn(str(self.path), h)
                except Exception:
                    pass
        return {"path": str(self.path), "hash": h, "version": self.version, "changed": changed,
                "reload": RELOAD_PROMPT}

    def read(self) -> str:
        return self.path.read_text(encoding="utf-8") if self.path.exists() else ""

    def _mirror(self, text: str) -> None:
        p = self.agents_md
        cur = p.read_text(encoding="utf-8") if p.exists() else ""
        block = f"{START}\n{text}\n{END}"
        if START in cur and END in cur:
            pre, rest = cur.split(START, 1)
            post = rest.split(END, 1)[1]
            new = pre + block + post
        else:
            new = (cur.rstrip() + "\n\n" if cur.strip() else "") + block + "\n"
        p.write_text(new, encoding="utf-8")
