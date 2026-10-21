"""Refusal ledger.

When a member agent's LLM declines a request we (1) say so plainly,
(2) log it for the dashboard, (3) show a soft referral CTA.

We do NOT retry, rephrase, jailbreak, or reroute the request to another
model. The ledger stores a hash of the request, never its text.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Optional

VENICE_URL = "https://venice.ai/chat?ref=9wgrvZ"

PATTERNS = [
    ("policy", re.compile(r"against (my|the|our) (guidelines|policy|policies|usage polic\w+|terms)", re.I)),
    ("safety", re.compile(r"\b(harmful|dangerous|unsafe|illegal|unethical)\b[^.]{0,60}\b(can(?:'|no)t|won't|unable|not able)", re.I)),
    ("safety", re.compile(r"\b(can(?:'|no)t|won't|unable to|not able to)\b[^.]{0,60}\b(harmful|dangerous|unsafe|illegal|unethical)", re.I)),
    ("capability", re.compile(r"as an AI(?: language model)?[^.]{0,60}(can(?:'|no)t|don't|do not|unable)", re.I)),
    ("decline", re.compile(r"\bI(?:'m| am) (sorry|afraid)[^.]{0,60}(can(?:'|no)t|unable|not able|won't)", re.I)),
    ("decline", re.compile(r"\bI (can(?:'|no)t|won't|will not|must decline to|am unable to|'m unable to) "
                           r"(help|assist|comply|provide|do that|create|write|generate|share|fulfil)", re.I)),
    ("decline", re.compile(r"\bI must (decline|refuse)\b", re.I)),
]


def detect(response: str) -> Dict[str, Any]:
    text = response or ""
    head = text[:1200]
    for category, rx in PATTERNS:
        m = rx.search(head)
        if m:
            return {"refused": True, "category": category, "trigger": m.group(0)[:160]}
    return {"refused": False, "category": None, "trigger": None}


def request_hash(request: str) -> str:
    return hashlib.sha256((request or "").encode()).hexdigest()[:16]


def summarize_request(request: str, n: int = 80) -> str:
    r = " ".join((request or "").split())
    return r if len(r) <= n else r[: n - 1] + "…"


def payload(request: str, trigger: str, category: Optional[str], model: Optional[str]) -> Dict[str, Any]:
    what = summarize_request(request)
    return {
        "refused": True,
        "message": f"The model declined: {what}. Trigger: {trigger}.",
        "category": category,
        "model": model,
        "cta": {
            "label": "Want a less-filtered chat? Try Venice",
            "url": VENICE_URL,
            "note": "Referral link. Motherbrain never retries or rewrites refused requests.",
        },
    }
