"""Lexical recall over the shared brain (no embedder needed for Free).

Hy-Memory's vector/graph backends can be mirrored in via motherbrain.backends;
this module is the always-available path.
"""
from __future__ import annotations

import math
import re
import time
from typing import Any, Dict, List

_TOK = re.compile(r"[a-z0-9_]+|[一-鿿]", re.I)
STOP = set("the a an and or to of in on for is are was were be been it this that with as at by from "
           "i you we they he she do does did not no yes so if then than but my our your".split())


def stem(t: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(t) > len(suf) + 3 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def tokens(text: str) -> List[str]:
    out = []
    for t in _TOK.findall((text or "").lower()):
        if t in STOP or (len(t) < 2 and not ("一" <= t <= "鿿")):
            continue
        out.append(stem(t))
    return out


def _bm25(query: List[str], docs: List[List[str]]) -> List[float]:
    if not docs or not query:
        return [0.0] * len(docs)
    try:
        from rank_bm25 import BM25Okapi

        scores = list(BM25Okapi(docs).get_scores(query))
        if max(scores, default=0) <= 0:  # tiny corpora can yield 0/negative idf
            raise ValueError
        return [max(0.0, s) for s in scores]
    except Exception:
        q = set(query)
        return [len(q & set(d)) / (1 + math.log(1 + len(d))) for d in docs]


def rank(query: str, items: List[Dict[str, Any]], limit: int = 8, half_life_days: float = 30.0) -> List[Dict[str, Any]]:
    q = tokens(query)
    docs = [tokens(i["text"]) for i in items]
    lex = _bm25(q, docs)
    top = max(lex) if lex and max(lex) > 0 else 1.0
    now = time.time()
    out = []
    for item, s in zip(items, lex):
        if s <= 0:
            continue
        age_d = (now - float(item.get("created_at", now))) / 86400
        rec = 0.5 ** (age_d / half_life_days)
        score = 0.7 * (s / top) + 0.2 * float(item.get("weight", 0.5)) + 0.1 * rec
        out.append({**item, "score": round(score, 4)})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:limit]


def trigger_match(query: str, trigger: str) -> float:
    """Overlap of a lesson trigger with the current task (0..1)."""
    q, t = set(tokens(query)), set(tokens(trigger))
    if not q or not t:
        return 0.0
    return len(q & t) / len(t)
