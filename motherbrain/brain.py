"""Motherbrain: one shared brain, many member agents."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import dream as dreamlib
from . import mood as moodlib
from . import refusal as refusallib
from .backends import load as load_backend
from .jev import JEV
from .llm import NoLLM, chat
from .recall import rank, trigger_match
from .router import Router
from .soul import RELOAD_PROMPT, Soul, render
from .store import Store, default_home

LESSON_KINDS = ("trauma", "hard_lesson", "win", "boundary")
LESSON_WEIGHT = {"trauma": 1.0, "hard_lesson": 0.9, "boundary": 0.7, "win": 0.6}
LONG_LABELS = ("fact", "lesson", "trauma")
TRIGGER_MATCH = 0.34
TOOLS = ["mb_write", "mb_search", "mb_lesson", "mb_state", "mb_evolve", "mb_jev", "mb_reload",
         "mb_refusal", "mb_join", "mb_members"]


def _messages_text(messages: List[Dict[str, Any]]) -> str:
    return "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages if m.get("content"))


def _trace_text(t: Dict[str, Any]) -> str:
    name = t.get("tool") or t.get("name") or "tool"
    args = t.get("args") or t.get("input") or {}
    res = t.get("error") or t.get("result") or t.get("output") or ""
    status = "ERROR" if t.get("error") else "ok"
    return f"tool {name}({json.dumps(args, ensure_ascii=False)[:300]}) -> {status}: {str(res)[:600]}"


class Motherbrain:
    def __init__(self, brain_id: Optional[str] = None, tier: Optional[str] = None, *,
                 db_path: Optional[str] = None, soul_path: Optional[str] = None,
                 agents_md: Optional[str] = None, use_llm: Optional[bool] = None,
                 short_keep: int = 50, name: Optional[str] = None):
        self.brain_id = brain_id or os.environ.get("MB_BRAIN", "default")
        self.store = Store(db_path or os.environ.get("MB_DB"))
        existing = self.store.one("SELECT tier FROM brains WHERE id=?", [self.brain_id])
        tier = tier or os.environ.get("MB_TIER") or (existing or {}).get("tier") or "free"
        self.router = Router(tier)
        self.brain = self.store.ensure_brain(self.brain_id, self.router.tier, name)
        if use_llm is None:
            use_llm = os.environ.get("MB_OFFLINE", "") not in ("1", "true", "yes")
        self.use_llm = use_llm
        self.jev = JEV(self.router, self.store, use_llm=use_llm)
        sp = soul_path or os.environ.get("MB_SOUL_PATH") or default_home() / "brains" / self.brain_id / "motherbrain.md"
        self.soul = Soul(Path(sp), agents_md or os.environ.get("MB_AGENTS_MD"))
        self.short_keep = short_keep
        self.backend = load_backend(self.brain_id)

    @property
    def tier(self) -> str:
        return self.router.tier

    # ------------------------------------------------------------ members
    def join(self, agent_id: str, kind: Optional[str] = None, role: Optional[str] = None) -> Dict[str, Any]:
        new = self.store.upsert_member(self.brain_id, agent_id, kind, role)
        if new:
            self.store.event(self.brain_id, "join", agent_id, kind=kind, role=role)
        soul = self._rewrite_soul("join")
        return {"brain_id": self.brain_id, "agent_id": agent_id, "new_member": new, "tier": self.tier,
                "members": [m["agent_id"] for m in self.store.members(self.brain_id)],
                "tools": TOOLS, "soul": soul,
                "instructions": f"You share this brain with the agents listed. {RELOAD_PROMPT} now."}

    def members(self) -> List[Dict[str, Any]]:
        return self.store.members(self.brain_id)

    # ------------------------------------------------------------ write
    def write(self, text: Optional[str] = None, *, agent_id: str, thread_id: Optional[str] = None,
              messages: Optional[List[Dict[str, Any]]] = None, tool_trace: Optional[Dict[str, Any]] = None,
              scene: Optional[str] = None, outcome: Optional[str] = None, model: Optional[str] = None,
              stage: Optional[str] = None) -> Dict[str, Any]:
        parts = [p for p in [text, _messages_text(messages) if messages else None,
                             _trace_text(tool_trace) if tool_trace else None] if p]
        body = "\n".join(parts).strip()
        if not body:
            raise ValueError("nothing to write: pass text, messages, or tool_trace")
        if tool_trace and not scene:
            scene = "tool_use"
        self.store.touch_member(self.brain_id, agent_id, wrote=True)
        j = self.jev.classify(body, hint=scene)
        scene = scene or j["scene"]
        label, prio = j["label"], j["priority"]
        if outcome == "fail" and label in ("fact", "junk", "mood"):
            label, prio = "trauma" if prio >= 4 else "lesson", max(prio, 4)
        result: Dict[str, Any] = {"label": label, "priority": prio, "scene": scene, "jev": j["source"],
                                  "agent_id": agent_id}

        sid = self.store.add_memory(brain_id=self.brain_id, agent_id=agent_id, thread_id=thread_id,
                                    stage="short", kind=label, scene=scene, text=body[:4000],
                                    weight=0.1 if label == "junk" else 0.4, priority=prio,
                                    meta={"outcome": outcome} if outcome else None)
        self.store.expire_short(self.brain_id, agent_id, thread_id, self.short_keep)
        result["short_id"] = sid

        refused = None
        if messages:
            assistant = "\n".join(m.get("content", "") for m in messages if m.get("role") == "assistant")
            user = "\n".join(m.get("content", "") for m in messages if m.get("role") == "user")
            if assistant:
                r = self.refusal(user, assistant, agent_id=agent_id, model=model)
                if r.get("refused"):
                    refused = result["refusal"] = r

        # Refused exchanges stay short-term only: a refusal is not identity.
        if not refused and stage != "short" and (stage == "long" or (label in LONG_LABELS and prio >= 2)):
            line = self._distill(body) if (messages or tool_trace or len(body) > 240) else body
            w = {"trauma": 0.95, "lesson": 0.8}.get(label, 0.5 + 0.08 * prio)
            lid = self.store.add_memory(brain_id=self.brain_id, agent_id=agent_id, thread_id=thread_id,
                                        stage="long", kind=label, scene=scene, text=line[:1200], weight=w,
                                        priority=prio, meta={"from_short": sid})
            result["long_id"] = lid
            self.store.event(self.brain_id, "memory", agent_id, stage="long", kind=label, text=line[:240],
                             scene=scene)
            if self.backend:
                self.backend.add(line, agent_id, scene)

        if outcome in ("fail", "ok"):
            self.store.event(self.brain_id, "task_outcome", agent_id, ok=outcome == "ok", text=body[:300])

        if j["mood"]:
            changed = moodlib.apply(self.store.mood(self.brain_id), delta=j["mood"])
            if changed:
                self.store.set_mood(self.brain_id, changed)
                self.store.event(self.brain_id, "mood", agent_id, changed=changed)
                result["soul"] = self._rewrite_soul("mood")
        return result

    def _distill(self, body: str) -> str:
        if not self.use_llm:
            return body
        chain = self.router.chain("long")
        if not chain:
            return body
        try:
            text, _ = chat(chain, [
                {"role": "system", "content": "Rewrite as ONE durable memory line (<=220 chars). Keep names, "
                                              "numbers, paths, errors. Third person. Output only the line."},
                {"role": "user", "content": body[:6000]}], max_tokens=120, temperature=0.1, timeout=20)
            return text.strip().strip('"') or body
        except NoLLM:
            return body

    # ------------------------------------------------------------ search
    def search(self, query: str, *, agent_id: str, thread_id: Optional[str] = None, mode: str = "normal",
               shared: bool = False, limit: int = 8) -> Dict[str, Any]:
        if mode not in ("normal", "profile", "proactive"):
            raise ValueError("mode must be normal | profile | proactive")
        self.store.touch_member(self.brain_id, agent_id)
        out: Dict[str, Any] = {"brain_id": self.brain_id, "mode": mode, "soul_hash": self.soul.hash}

        # Lessons first: inject before planning on similar trigger (all modes).
        matched = []
        for l in self.store.lessons(self.brain_id):
            s = trigger_match(query, l["trigger"])
            threshold = TRIGGER_MATCH if l["kind"] in ("trauma", "hard_lesson") else 0.5
            if s >= threshold or (mode == "proactive" and s >= 0.25):
                matched.append({**l, "match": round(s, 3), "from_peer": l["agent_id"] != agent_id})
        matched.sort(key=lambda l: (l["match"] * l["weight"]), reverse=True)
        matched = matched[: max(3, limit // 2)]
        for l in matched:
            self.store.hit_lesson(l["id"])
            self.store.event(self.brain_id, "lesson_applied", agent_id, lesson_id=l["id"], trigger=l["trigger"],
                             kind=l["kind"], author=l["agent_id"])
        out["lessons"] = [{k: l[k] for k in ("id", "kind", "trigger", "rule", "consequence", "weight",
                                             "agent_id", "match", "from_peer")} for l in matched]
        if matched:
            out["before_planning"] = "Apply these lessons before you plan: " + " | ".join(
                f"when {l['trigger']} -> {l['rule']}" for l in matched)

        if mode == "profile":
            ident = self.store.memories(self.brain_id, stages=["long", "dream"], limit=200)
            ident.sort(key=lambda m: (m["weight"], m["created_at"]), reverse=True)
            out["identity"] = [self._pub(m, agent_id) for m in ident[:limit]]
            out["mood"] = moodlib.merged(self.store.mood(self.brain_id))
            return out

        pool = self.store.memories(self.brain_id, stages=["long", "dream"], limit=2000)
        pool += self.store.memories(self.brain_id, stages=["short"], limit=500,
                                    agent_id=None if shared else agent_id,
                                    thread_id=None if shared else thread_id)
        hits = rank(query, pool, limit=limit)
        if self.backend:
            hits += self.backend.search(query, max(2, limit // 2))
        out["memories"] = [self._pub(m, agent_id) for m in hits]
        out["peers_contributed"] = sorted({m["agent_id"] for m in hits if m["agent_id"] != agent_id})
        return out

    @staticmethod
    def _pub(m: Dict[str, Any], caller: str) -> Dict[str, Any]:
        return {"id": m.get("id"), "text": m["text"], "stage": m["stage"], "kind": m["kind"],
                "scene": m.get("scene"), "agent_id": m["agent_id"], "from_peer": m["agent_id"] != caller,
                "score": m.get("score"), "created_at": m.get("created_at")}

    # ------------------------------------------------------------ lessons
    def lesson(self, *, agent_id: str, kind: str, trigger: str, rule: str, consequence: Optional[str] = None,
               weight: Optional[float] = None, expires_days: Optional[float] = None) -> Dict[str, Any]:
        if kind not in LESSON_KINDS:
            raise ValueError(f"kind must be one of {LESSON_KINDS}")
        if not trigger.strip() or not rule.strip():
            raise ValueError("trigger and rule are required")
        self.store.touch_member(self.brain_id, agent_id, wrote=True)
        expires = None if kind == "trauma" or not expires_days else time.time() + expires_days * 86400
        w = float(weight if weight is not None else LESSON_WEIGHT[kind])
        if kind in ("trauma", "hard_lesson"):
            w = max(w, 0.8)
        lid = self.store.add_lesson(brain_id=self.brain_id, agent_id=agent_id, kind=kind, trigger=trigger,
                                    consequence=consequence, rule=rule, weight=w, expires=expires)
        self.store.add_memory(brain_id=self.brain_id, agent_id=agent_id, stage="long",
                              kind="trauma" if kind == "trauma" else "lesson", scene=None,
                              text=f"[{kind}] when {trigger} -> {rule}" + (f" (last time: {consequence})" if consequence else ""),
                              weight=w, priority=5 if kind in ("trauma", "hard_lesson") else 3, meta={"lesson_id": lid})
        self.store.event(self.brain_id, "lesson_written", agent_id, lesson_id=lid, kind=kind, trigger=trigger,
                         rule=rule, consequence=consequence)
        delta = {"trauma": {"caution": 0.15, "trauma_level": 0.1, "confidence": -0.05},
                 "hard_lesson": {"caution": 0.1},
                 "win": {"pride": 0.1, "confidence": 0.05, "hope": 0.05},
                 "boundary": {"stubbornness": 0.05}}[kind]
        changed = moodlib.apply(self.store.mood(self.brain_id), delta=delta)
        if changed:
            self.store.set_mood(self.brain_id, changed)
        return {"lesson_id": lid, "kind": kind, "weight": w, "shared_with": [m["agent_id"] for m in self.members()],
                "soul": self._rewrite_soul("lesson")}

    def lessons(self) -> List[Dict[str, Any]]:
        return self.store.lessons(self.brain_id)

    # ------------------------------------------------------------ mood
    def state(self, *, agent_id: Optional[str] = None, delta: Optional[Dict[str, float]] = None,
              set: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if delta or set:
            changed = moodlib.apply(self.store.mood(self.brain_id), delta=delta, set_=set)
            if changed:
                self.store.set_mood(self.brain_id, changed)
                self.store.event(self.brain_id, "mood", agent_id, changed=changed)
                out["soul"] = self._rewrite_soul("mood")
            out["changed"] = changed
        m = moodlib.merged(self.store.mood(self.brain_id))
        out.update({"mood": m, "chips": moodlib.chips(m), "tone": moodlib.tone_lines(m),
                    "note": "Mood is tone only; it never blocks tools or legitimate work."})
        return out

    # ------------------------------------------------------------ dream
    def evolve(self, *, agent_id: Optional[str] = None) -> Dict[str, Any]:
        short = self.store.memories(self.brain_id, stages=["short"], include_expired=True, undreamed=True, limit=400)
        long = self.store.memories(self.brain_id, stages=["long"], limit=400)
        lessons = self.store.lessons(self.brain_id)
        d, power = dreamlib.run(self.router.chain("dream"), short, long, lessons, use_llm=self.use_llm)
        promoted = 0
        for f in d["facts"]:
            self.store.add_memory(brain_id=self.brain_id, agent_id="dream", stage="long", kind="fact",
                                  text=f, weight=0.7, priority=3, meta={"source": "dream"})
            promoted += 1
        new_lessons = 0
        for l in d["lessons"]:
            kind = l.get("kind") if l.get("kind") in ("hard_lesson", "win", "boundary") else "hard_lesson"
            self.store.add_lesson(brain_id=self.brain_id, agent_id="dream", kind=kind, trigger=str(l["trigger"])[:200],
                                  consequence=(str(l.get("consequence"))[:200] if l.get("consequence") else None),
                                  rule=str(l["rule"])[:300], weight=LESSON_WEIGHT[kind])
            new_lessons += 1
        self.store.expire(d["drop"])
        self.store.mark_dreamed([m["id"] for m in short])
        if d.get("mood"):
            changed = moodlib.apply(self.store.mood(self.brain_id),
                                    delta={k: max(-0.3, min(0.3, float(v))) for k, v in d["mood"].items()
                                           if isinstance(v, (int, float))})
            if changed:
                self.store.set_mood(self.brain_id, changed)
        self.store.add_memory(brain_id=self.brain_id, agent_id="dream", stage="dream", kind="summary",
                              text=d["summary"], weight=0.75, priority=4, meta={"power": power})
        self.store.event(self.brain_id, "dream", agent_id, summary=d["summary"], promoted=promoted,
                         lessons=new_lessons, merged=len(d["drop"]), power=power, tier=self.tier)
        return {"summary": d["summary"], "promoted": promoted, "new_lessons": new_lessons, "merged": len(d["drop"]),
                "consolidated": len(short), "brain_power": power, "tier": self.tier,
                "soul": self._rewrite_soul("evolve")}

    # ------------------------------------------------------------ refusal
    def refusal(self, request: str, response: str, *, agent_id: Optional[str] = None,
                model: Optional[str] = None) -> Dict[str, Any]:
        det = refusallib.detect(response)
        if not det["refused"]:
            return {"refused": False}
        why = refusallib.explain(request, response)
        if self.use_llm and (not why["reason"] or not why["flagged"]):
            why = self._explain_llm(request, response, why)
        rid = self.store.add_refusal(brain_id=self.brain_id, agent_id=agent_id,
                                     request_hash=refusallib.request_hash(request), trigger=det["trigger"],
                                     category=det["category"], model=model, outcome="declined",
                                     excerpt=refusallib.excerpt(request), reason=why.get("reason"),
                                     topic=why.get("topic"), flagged=why.get("flagged"))
        self.store.event(self.brain_id, "refusal", agent_id, refusal_id=rid, category=det["category"], model=model,
                         topic=why.get("topic"), flagged=why.get("flagged"))
        p = refusallib.payload(request, det["trigger"], det["category"], model, why)
        p["ledger_id"] = rid
        return p

    def _explain_llm(self, request: str, response: str, why: Dict[str, Any]) -> Dict[str, Any]:
        """JEV-sized call (mini): why it declined + which request words it reacted to. Explanation only."""
        chain = self.router.chain("jev")
        if not chain:
            return why
        from .llm import chat_json
        try:
            d, _ = chat_json(chain, [
                {"role": "system", "content": 'An AI model declined a request. Explain to the user, JSON only: '
                 '{"why":"<=14 words, plain reason","terms":["1-3 words or short phrases copied from the REQUEST '
                 'that most likely caused it"]}'},
                {"role": "user", "content": "REQUEST: " + refusallib.redact(request)[:1500] +
                 "\nRESPONSE: " + response[:1200]}], max_tokens=64, temperature=0.0, timeout=5)
        except Exception:
            return why
        req_l = (request or "").lower()
        terms = [str(t).strip().lower()[:40] for t in (d.get("terms") or []) if str(t).strip().lower() in req_l]
        out = dict(why)
        if d.get("why") and not out.get("reason"):
            out["reason"] = str(d["why"]).strip().rstrip(".")[:160]
        merged: List[str] = []
        for w in terms + why.get("flagged", []):
            if not any(w in m or m in w for m in merged):
                merged.append(w)
        out["flagged"] = merged[:3]
        return out

    # ------------------------------------------------------------ soul
    def _rewrite_soul(self, reason: str) -> Dict[str, Any]:
        ident = [m for m in self.store.memories(self.brain_id, stages=["long"], limit=300) if m["kind"] == "fact"]
        ident.sort(key=lambda m: (m["weight"], m["created_at"]), reverse=True)
        last_dream = self.store.memories(self.brain_id, stages=["dream"], limit=1)
        text = render(self.brain, self.members(), self.store.mood(self.brain_id), self.lessons(), ident,
                      last_dream[0]["text"] if last_dream else None)
        info = self.soul.write(text)
        if info["changed"]:
            self.store.event(self.brain_id, "soul_changed", None, reason=reason, hash=info["hash"])
        return info

    def reload(self) -> Dict[str, Any]:
        if not self.soul.path.exists():
            self._rewrite_soul("reload")
        return {"path": str(self.soul.path), "hash": self.soul.hash, "soul": self.soul.read()}

    # ------------------------------------------------------------ dashboard
    def before_after(self) -> List[Dict[str, Any]]:
        outcomes = self.store.events(self.brain_id, limit=5000, types=["task_outcome"])
        out = []
        for l in self.store.lessons(self.brain_id, include_expired=True):
            rel = [e for e in outcomes if trigger_match(e["payload"].get("text", ""), l["trigger"]) >= TRIGGER_MATCH]
            before = [e for e in rel if e["ts"] < l["created_at"]]
            after = [e for e in rel if e["ts"] >= l["created_at"]]
            out.append({
                "lesson_id": l["id"], "kind": l["kind"], "trigger": l["trigger"], "rule": l["rule"],
                "author": l["agent_id"], "created_at": l["created_at"], "applied": l["hits"],
                "fails_before": sum(1 for e in before if not e["payload"].get("ok")),
                "fails_after": sum(1 for e in after if not e["payload"].get("ok")),
                "ok_after": sum(1 for e in after if e["payload"].get("ok")),
                "ok_after_agents": sorted({e["agent_id"] for e in after if e["payload"].get("ok")}),
            })
        return out

    def timeline(self, limit: int = 100) -> List[Dict[str, Any]]:
        ev = self.store.events(self.brain_id, limit=limit,
                               types=["memory", "lesson_written", "dream", "join", "refusal", "task_outcome",
                                      "lesson_applied", "mood"])
        return [{"ts": e["ts"], "type": e["type"], "agent_id": e["agent_id"], **e["payload"]} for e in ev]

    def snapshot(self) -> Dict[str, Any]:
        st = self.state()
        refusals = self.store.refusals(self.brain_id)
        by_day: Dict[str, int] = {}
        for r in refusals:
            d = time.strftime("%Y-%m-%d", time.gmtime(r["ts"]))
            by_day[d] = by_day.get(d, 0) + 1
        counts = {s: len(self.store.memories(self.brain_id, stages=[s], limit=100000)) for s in ("short", "long", "dream")}
        return {
            "brain": {"id": self.brain_id, "name": self.brain.get("name"), "tier": self.tier},
            "router": self.router.describe(),
            "members": self.members(),
            "counts": {**counts, "lessons": len(self.lessons()), "refusals": len(refusals)},
            "mood": st["mood"], "chips": st["chips"], "tone": st["tone"],
            "soul": self.reload()["soul"],
            "lessons": self.lessons(),
            "timeline": self.timeline(),
            "refusals": refusals,
            "refusals_by_day": [{"day": k, "count": v} for k, v in sorted(by_day.items())],
            "before_after": self.before_after(),
            "cta": {"venice": refusallib.VENICE_URL},
        }
