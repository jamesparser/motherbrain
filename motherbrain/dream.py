"""Dream state (System 2): consolidate, reconcile, ask "what did we learn".

Runs on the strongest model the tier allows (Free: mini). Falls back to a
deterministic consolidation so it never dead-ends.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from .llm import NoLLM, chat_json

SYSTEM = (
    "You are the dream state of a brain shared by several AI agents. Consolidate recent memories.\n"
    "Return ONE JSON object:\n"
    '{"facts":["durable fact, one line, keep specifics"],'
    '"lessons":[{"kind":"hard_lesson|win|boundary","trigger":"when this situation recurs","rule":"what to do",'
    '"consequence":"what happened last time"}],'
    '"drop":["ids of long-term items now redundant or contradicted"],'
    '"mood":{"<field>":<-0.3..0.3>},"summary":"2-3 sentences: what the fleet learned"}\n'
    "Only include lessons clearly supported by the memories. Never invent facts."
)


def _norm(t: str) -> str:
    return re.sub(r"\W+", " ", (t or "").lower()).strip()


def heuristic(short: List[Dict[str, Any]], long: List[Dict[str, Any]]) -> Dict[str, Any]:
    long_norm = {_norm(m["text"]) for m in long}
    facts, seen = [], set()
    for m in sorted(short, key=lambda m: -m["priority"]):
        n = _norm(m["text"])
        if m["kind"] == "junk" or m["priority"] < 3 or n in long_norm or n in seen:
            continue
        seen.add(n)
        facts.append(m["text"])
    by: Dict[str, List[Dict[str, Any]]] = {}
    for m in long:
        by.setdefault(_norm(m["text"]), []).append(m)
    drop = []
    for group in by.values():
        if len(group) > 1:
            group.sort(key=lambda m: m["created_at"], reverse=True)
            drop += [m["id"] for m in group[1:]]
    agents = sorted({m["agent_id"] for m in short + long})
    summary = (f"Consolidated {len(short) + len(long)} memories from {len(agents)} agent(s): "
               f"promoted {len(facts)}, merged {len(drop)} duplicate(s).")
    return {"facts": facts, "lessons": [], "drop": drop, "mood": {}, "summary": summary, "source": "heuristic"}


def run(chain, short: List[Dict[str, Any]], long: List[Dict[str, Any]], lessons: List[Dict[str, Any]],
        use_llm: bool = True) -> Tuple[Dict[str, Any], str]:
    fb = heuristic(short, long)
    if not use_llm or not chain or not (short or long):
        return fb, "heuristic"
    def fmt(ms):
        return [{"id": m["id"], "agent": m["agent_id"], "kind": m["kind"], "text": m["text"][:400]} for m in ms]
    payload = {"short_term": fmt(short[:80]), "long_term": fmt(long[:80]),
               "known_lessons": [{"trigger": l["trigger"], "rule": l["rule"]} for l in lessons[:30]]}
    try:
        d, ep = chat_json(chain, [{"role": "system", "content": SYSTEM},
                                  {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                          max_tokens=1200, temperature=0.2, timeout=90)
    except (NoLLM, ValueError):
        return fb, "heuristic"
    long_ids = {m["id"] for m in long}
    out = {
        "facts": [str(f)[:400] for f in d.get("facts", []) if str(f).strip()][:40],
        "lessons": [l for l in d.get("lessons", []) if isinstance(l, dict) and l.get("trigger") and l.get("rule")][:10],
        "drop": [i for i in d.get("drop", []) if i in long_ids],
        "mood": d.get("mood") or {},
        "summary": str(d.get("summary") or fb["summary"])[:600],
        "source": "llm",
    }
    return out, ep.power
