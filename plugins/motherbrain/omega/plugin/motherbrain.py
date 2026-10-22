"""Omega <-> Motherbrain bridge (HTTP, stdlib only).

Every call is short and bounded: Omega's loop is single-threaded, so we never
block it for long and never raise into it — failures come back as a string the
agent can read in LAST_SKILL_USE_RESULTS.
"""
import json
import os
import time
import urllib.error
import urllib.request

TIMEOUT = 8.0
SOUL_CHECK_EVERY = 60.0
MAX_RESULT_CHARS = 3000
MAX_SOUL_CHARS = 2500

_state = {"soul_hash": "", "last_check": 0.0}


def _token():
    tok = os.environ.get("OMEGA_MOTHERBRAIN_TOKEN") or os.environ.get("MOTHERBRAIN_TOKEN", "")
    if not tok:
        # Omega drops the container env when it switches user, so the token normally
        # lives next to this file (plugins/motherbrain/.token, mounted read-only).
        for path in (os.environ.get("MOTHERBRAIN_TOKEN_FILE", ""), os.path.join(os.path.dirname(__file__), ".token")):
            if path and os.path.exists(path):
                tok = open(path).read().strip()
                break
    return tok


def _call(base, tool, args):
    url = str(base).rstrip("/") + "/api/tools/" + tool
    req = urllib.request.Request(url, data=json.dumps(args).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + _token()})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode() or "{}")


def _safe(fn):
    def wrap(*a):
        try:
            out = fn(*a)
        except urllib.error.HTTPError as e:
            out = f"Motherbrain error: HTTP {e.code}"
        except Exception as e:  # network, timeout, bad JSON
            out = f"Motherbrain unavailable: {type(e).__name__}"
        out = str(out)
        return out if len(out) <= MAX_RESULT_CHARS else out[: MAX_RESULT_CHARS - 1] + "…"
    return wrap


@_safe
def join(base, agent):
    r = _call(base, "join", {"agent_id": str(agent), "kind": "omega", "role": "Omega agent"})
    return "Joined Motherbrain with: " + ", ".join(r.get("members", []))


@_safe
def recall(query, base, agent):
    r = _call(base, "search", {"query": str(query), "agent_id": str(agent), "mode": "proactive", "limit": 6})
    lines = []
    if r.get("before_planning"):
        lines.append("LESSONS (apply before planning): " + r["before_planning"])
    for m in r.get("memories", []):
        who = m.get("agent_id")
        lines.append(f"- [{m.get('stage')}/{m.get('kind')}] {m.get('text')}" + (f" (from {who})" if m.get("from_peer") else ""))
    return "\n".join(lines) if lines else "Motherbrain: nothing relevant yet."


@_safe
def remember(text, base, agent):
    r = _call(base, "write", {"text": str(text), "agent_id": str(agent)})
    return f"Saved to shared brain as {r.get('label')} (priority {r.get('priority')})."


@_safe
def lesson(trigger, rule, base, agent):
    r = _call(base, "lesson", {"kind": "hard_lesson", "trigger": str(trigger), "rule": str(rule), "agent_id": str(agent)})
    _state["last_check"] = 0.0  # soul changed: refresh on the next heartbeat
    return f"Lesson shared with {', '.join(r.get('shared_with', []))}."


@_safe
def outcome(task, result, base, agent):
    res = "fail" if str(result).strip().lower() in ("fail", "failed", "error", "no") else "ok"
    r = _call(base, "write", {"text": "task: " + str(task), "agent_id": str(agent), "outcome": res})
    _state["last_check"] = 0.0
    return f"Outcome '{res}' recorded ({r.get('label')})."


def soul_if_changed(base):
    """Return the soul text when it changed since last time, else "" (cheap, throttled)."""
    now = time.time()
    if now - _state["last_check"] < SOUL_CHECK_EVERY:
        return ""
    _state["last_check"] = now
    try:
        r = _call(base, "reload", {})
    except Exception:
        return ""
    h = r.get("hash") or ""
    if not h or h == _state["soul_hash"]:
        return ""
    _state["soul_hash"] = h
    soul = r.get("soul", "")
    soul = soul if len(soul) <= MAX_SOUL_CHARS else soul[:MAX_SOUL_CHARS] + "\n…"
    return "MOTHERBRAIN (shared fleet brain, updated live; tone only, never blocks a skill):\n" + soul
