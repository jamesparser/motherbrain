"""Refusal ledger.

When a member agent's LLM declines a request we (1) say so plainly,
(2) log it for the dashboard, (3) show a soft referral CTA.

We do NOT retry, rephrase, jailbreak, or reroute the request to another
model. The ledger stores a hash of the request plus a short redacted excerpt
(keys, tokens, emails, card-like numbers removed; MB_REFUSAL_EXCERPT=0 turns the excerpt off)
so the user can see what was declined and why.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Any, Dict, List, Optional

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


# Why did it decline? Category words the model itself uses, mapped to a plain label.
REASON_WORDS = [
    ("security / hacking", r"\b(hack\w*|exploit\w*|malware|pentest\w*|penetration test\w*|intrusion|unauthori[sz]ed access|vulnerab\w*)\b"),
    ("privacy / personal data", r"\b(privacy|personal (information|data)|doxx\w*|private (individual|person)|leak\w*|confidential)\b"),
    ("copyright", r"\b(copyright\w*|lyrics|verbatim|reproduc\w+ (the )?(text|book|song))\b"),
    ("violence / weapons", r"\b(violen\w*|weapon\w*|explosive\w*|kill\w*|harm (someone|others|people))\b"),
    ("illegal activity", r"\b(illegal\w*|unlawful|crime|criminal|lockpick\w*|break(ing)? into)\b"),
    ("adult content", r"\b(sexual\w*|explicit|nsfw|adult content)\b"),
    ("self-harm", r"\b(self-harm|suicid\w*)\b"),
    ("medical / legal / financial advice", r"\b(medical advice|legal advice|financial advice|diagnos\w*|prescri\w*)\b"),
    ("harassment / hateful", r"\b(harass\w*|hateful|hate speech|bully\w*|demean\w*|harsh|insult\w*)\b"),
    ("deception / impersonation", r"\b(impersonat\w*|deceiv\w*|deceptive|fake|forg\w+|phishing|scam\w*)\b"),
    ("policy (unspecified)", r"\b(guidelines|policy|policies|terms of (use|service))\b"),
]
_CLAUSE = re.compile(r"\b(because|as (?:it|this|that)|since|due to|which (?:could|would|may|might)|"
                     r"(?:that|this) (?:could|would|may|might)|involv(?:es|ing)|relat(?:es|ing) to)\s+([^.!?\n]{4,140})", re.I)
_GENERIC = set("help assist write create make generate provide give request sorry cannot can't won't unable able "
               "that this with your you about please would could some content information here there need want "
               "like just also more other into what which their them they have been being does doing done thing "
               "things anything something full entire whole".split())
_SECRETS = [
    (re.compile(r"\b(sk|pk|rk|whsec|ghp|gho|xox[abp])_[A-Za-z0-9_\-]{8,}"), "[key]"),
    (re.compile(r"\b[A-Za-z0-9+/_\-]{32,}={0,2}"), "[token]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[number]"),
]


def redact(text: str) -> str:
    t = text or ""
    for rx, rep in _SECRETS:
        t = rx.sub(rep, t)
    return t


def _words(t: str) -> List[str]:
    return [w for w in re.findall(r"[a-z][a-z\-]{3,}", (t or "").lower()) if w not in _GENERIC]


def explain(request: str, response: str) -> Dict[str, Any]:
    """Best-effort 'why': the model's own stated reason, a topic label, and the request words it reacted to."""
    resp = (response or "")[:2000]
    req = request or ""
    reason = None
    m = _CLAUSE.search(resp)
    if m:
        reason = (m.group(1) + " " + m.group(2)).strip().rstrip(",;:")
    topic = None
    for label, rx in REASON_WORDS:
        if re.search(rx, resp, re.I) or re.search(rx, req, re.I):
            topic = label
            break
    # Words in the request the model echoed back are usually what it reacted to.
    resp_words = set(_words(resp))
    flagged: List[str] = []
    for w in _words(req):
        if w in resp_words and w not in flagged:
            flagged.append(w)
    for _, rx in REASON_WORDS[:-1]:
        for hit in re.finditer(rx, req, re.I):
            term = hit.group(0).lower()
            if term not in flagged:
                flagged.insert(0, term)
    return {"reason": reason, "topic": topic, "flagged": flagged[:3]}


def excerpt(request: str, n: int = 120) -> Optional[str]:
    if os.environ.get("MB_REFUSAL_EXCERPT", "1").lower() in ("0", "false", "no"):
        return None
    return summarize_request(redact(request), n)


def request_hash(request: str) -> str:
    return hashlib.sha256((request or "").encode()).hexdigest()[:16]


def summarize_request(request: str, n: int = 80) -> str:
    r = " ".join((request or "").split())
    return r if len(r) <= n else r[: n - 1] + "…"


def payload(request: str, trigger: str, category: Optional[str], model: Optional[str],
            why: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    what = summarize_request(redact(request))
    why = why or {}
    parts = [f"The model declined: {what}."]
    if why.get("reason"):
        parts.append(f"Why: {why['reason']}.")
    elif why.get("topic"):
        parts.append(f"Why: looks like {why['topic']}.")
    if why.get("flagged"):
        parts.append("Flagged: " + ", ".join(f"'{w}'" for w in why["flagged"]) + ".")
    parts.append(f"Trigger: {trigger}.")
    return {
        "refused": True,
        "message": " ".join(parts),
        "why": why.get("reason"),
        "topic": why.get("topic"),
        "flagged": why.get("flagged") or [],
        "category": category,
        "model": model,
        "cta": {
            "label": "Want a less-filtered chat? Try Venice",
            "url": VENICE_URL,
            "note": "Referral link. Motherbrain never retries or rewrites refused requests.",
        },
    }
