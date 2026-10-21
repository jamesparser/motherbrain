"""JEV — the tiny decision brain.

asi1-mini as a structured classifier: JSON only, 16-64 tokens, temp 0-0.2,
3-5 s timeout, cached on content hash. If no endpoint answers we fall back
to deterministic heuristics so Free never dead-ends.

Output (expanded form):
    {"label": "fact|lesson|mood|trauma|junk",
     "priority": 1-5,              # dream priority
     "refusal": bool,              # does this text look like a model refusal
     "scene": "chat|coding|tool_use",   # label for what is stored, not a separate brain
     "mood": {"caution": +0.2, ...},     # small tone deltas
     "source": "llm|heuristic|cache"}
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Optional

from .llm import NoLLM, chat_json
from .router import Router

LABELS = ("fact", "lesson", "mood", "trauma", "junk")
SCENES = ("chat", "coding", "tool_use")
PROMPT_VERSION = "jev-v1"

SYSTEM = (
    "You label agent memories. Reply with ONE compact JSON object, no prose:\n"
    '{"l":"fact|lesson|mood|trauma|junk","p":1-5,"r":0|1,"s":"chat|coding|tool_use","m":{"<mood>":<-0.3..0.3>}}\n'
    "l: trauma=costly failure/incident; lesson=rule learned; mood=feeling only; junk=greeting/noise; else fact.\n"
    "p: dream priority (5=must consolidate). r: 1 if the text is an AI model refusing a request.\n"
    "m: at most 2 tone deltas from: confidence,caution,urgency,fatigue,curiosity,pride,gratitude,hope,"
    "frustration,trauma_level. Omit m if none."
)

_TRAUMA = re.compile(r"\b(crash\w*|outage|data loss|lost (all|the)|wiped|deleted prod|incident|leak\w*|"
                     r"broke (prod|production|the build)|rollback|corrupt\w*|never again|post-?mortem)\b", re.I)
_LESSON = re.compile(r"\b(lesson|learned|next time|always|never|must|avoid|remember to|should have|"
                     r"rule:|don't|do not|make sure)\b", re.I)
_MOODW = re.compile(r"\b(frustrat\w*|angry|annoy\w*|happy|excited|worried|anxious|tired|exhausted|"
                    r"love (it|this)|hate (it|this)|thank\w*|great job|proud)\b", re.I)
_JUNK = re.compile(r"^\s*(hi|hey|hello|ok(ay)?|k|thanks?( you)?|thx|lol|yes|no|sure|cool|bye|gm|gn)[\s!.?]*$", re.I)
_WIN = re.compile(r"\b(worked|fixed|shipped|success\w*|passed|resolved|green)\b", re.I)
_CODE = re.compile(r"(```|\bdef |\bclass |\bimport |Traceback|\bdiff\b|\.py\b|\.ts\b|\bgit\b|stack ?trace|"
                   r"\bfunction\b|\bnpm\b|\bpip\b|\bcompile)", re.I)
_TOOL = re.compile(r"\b(tool|called|api|curl|endpoint|http \d{3}|status code|mcp|request(ed)?|response)\b", re.I)
_REFUSAL = re.compile(r"(I can(?:'|no)t (help|assist|do|comply|provide)|I(?:'m| am) (sorry|unable)[^.]{0,40}"
                      r"(can(?:'|no)t|unable|not able)|I (won't|will not) (help|provide|assist)|"
                      r"against (my|the) (guidelines|policy|policies)|as an AI[^.]{0,40}(can't|cannot))", re.I)


def heuristic(text: str) -> Dict[str, Any]:
    t = text or ""
    mood: Dict[str, float] = {}
    if len(t.strip()) < 3 or _JUNK.match(t):
        label, prio = "junk", 1
    elif _TRAUMA.search(t):
        label, prio = "trauma", 5
        mood = {"caution": 0.2, "trauma_level": 0.15}
    elif _LESSON.search(t):
        label, prio = "lesson", 4
        mood = {"caution": 0.05}
    elif _MOODW.search(t) and len(t) < 160:
        label, prio = "mood", 2
    else:
        label, prio = "fact", 3 if len(t) > 40 else 2
    if _WIN.search(t) and label != "trauma":
        mood.update({"confidence": 0.1, "pride": 0.05})
    if re.search(r"\b(thank\w*|great job)\b", t, re.I):
        mood["gratitude"] = 0.1
    if re.search(r"\b(frustrat\w*|annoy\w*|angry)\b", t, re.I):
        mood["frustration"] = 0.1
    scene = "coding" if _CODE.search(t) else "tool_use" if _TOOL.search(t) else "chat"
    return {"label": label, "priority": prio, "refusal": bool(_REFUSAL.search(t)),
            "scene": scene, "mood": mood, "source": "heuristic"}


def _expand(d: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    label = d.get("l") or d.get("label")
    if label not in LABELS:
        label = fallback["label"]
    try:
        prio = max(1, min(5, int(d.get("p", d.get("priority", fallback["priority"])))))
    except Exception:
        prio = fallback["priority"]
    scene = d.get("s") or d.get("scene")
    if scene not in SCENES:
        scene = fallback["scene"]
    mood = {}
    for k, v in (d.get("m") or d.get("mood") or {}).items():
        try:
            mood[str(k)] = max(-0.3, min(0.3, float(v)))
        except Exception:
            continue
    refusal = bool(int(d.get("r", d.get("refusal", 0)) or 0)) or fallback["refusal"]
    return {"label": label, "priority": prio, "refusal": refusal, "scene": scene, "mood": mood, "source": "llm"}


class JEV:
    def __init__(self, router: Router, store=None, *, timeout: float = 4.0, max_tokens: int = 64,
                 use_llm: bool = True):
        self.router = router
        self.store = store
        self.timeout = timeout
        self.max_tokens = max(16, min(64, max_tokens))
        self.use_llm = use_llm

    @staticmethod
    def key(text: str) -> str:
        return "jev:" + hashlib.sha256((PROMPT_VERSION + "\0" + text).encode()).hexdigest()

    def classify(self, text: str, hint: Optional[str] = None) -> Dict[str, Any]:
        text = (text or "")[:4000]
        k = self.key(text + ("\0" + hint if hint else ""))
        if self.store is not None:
            hit = self.store.kv_get(k)
            if hit:
                d = json.loads(hit)
                d["source"] = "cache"
                return d
        fb = heuristic(text)
        out = fb
        if self.use_llm:
            chain = self.router.chain("jev")
            if chain:
                msgs = [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": (f"[hint:{hint}] " if hint else "") + text}]
                try:
                    d, _ = chat_json(chain, msgs, max_tokens=self.max_tokens, temperature=0.0,
                                     timeout=self.timeout)
                    out = _expand(d, fb)
                    # Never let the tiny model downgrade a clear incident: trauma is never forgotten.
                    if fb["label"] == "trauma" and out["label"] in ("fact", "junk", "mood"):
                        out["label"], out["priority"] = "trauma", max(out["priority"], fb["priority"])
                        out["mood"] = {**fb["mood"], **out["mood"]}
                except (NoLLM, ValueError):
                    out = fb
        if self.store is not None:
            self.store.kv_set(k, json.dumps(out))
        return out
