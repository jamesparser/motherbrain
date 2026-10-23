"""Two real LLM agents sharing one Motherbrain, over MCP. Used for the demo video.

Agent `scout` gets a data-export task, plans with the LLM (asi1 when configured, else asi1-mini), calls real tools against a
real SQLite database, hits a real error, reflects, and records a hard lesson.
Agent `ops` (never saw that failure) gets a similar task, recalls the lesson before
planning, and succeeds. Then the brain dreams.

    cd /opt/motherbrain && set -a && . ./.env.demo && set +a && \
      .venv/bin/python scripts/live_agents.py --start-at <epoch> --mcp http://127.0.0.1:8791/mcp

Every LLM call and tool call is real; nothing is scripted except the two task prompts and pacing.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import shutil
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from motherbrain.llm import chat_json  # noqa: E402
from motherbrain.router import Router  # noqa: E402

from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamablehttp_client  # noqa: E402

ROOT = Path("/tmp/mb-live-demo")


# ----------------------------------------------------------------- real tools (sandboxed)
def setup_sandbox() -> Path:
    shutil.rmtree(ROOT, ignore_errors=True)
    (ROOT / "exports").mkdir(parents=True)
    db = sqlite3.connect(ROOT / "shop.db")
    db.execute("create table customers(id integer primary key, name text, email text, country text, ltv real)")
    db.execute("create table orders(id integer primary key, customer_id int, total real, created text)")
    random.seed(4)
    names = ["Ana Lima", "Bo Chen", "Chidi Okafor", "Dara Sok", "Eva Novak", "Farid Haddad", "Gita Rao", "Hiro Sato"]
    for i, n in enumerate(names, 1):
        db.execute("insert into customers values(?,?,?,?,?)",
                   (i, n, n.lower().replace(" ", ".") + "@example.com", random.choice(["KH", "US", "DE", "JP"]), round(random.uniform(40, 900), 2)))
    for i in range(1, 41):
        db.execute("insert into orders values(?,?,?,?)", (i, random.randint(1, 8), round(random.uniform(5, 300), 2), f"2026-10-{random.randint(1, 21):02d}"))
    db.commit()
    return ROOT


PII_COLUMNS = {"customers": ["name", "email"]}


def tool_list_tables(**_ignored) -> str:
    db = sqlite3.connect(ROOT / "shop.db")
    rows = db.execute("select name from sqlite_master where type='table'").fetchall()
    return ", ".join(r[0] for r in rows)


def tool_export_table(table: str, path: str, redact_pii: bool = False) -> str:
    target = (ROOT / "exports" / path).resolve()
    if ROOT not in target.parents:
        raise PermissionError("path must stay inside exports/")
    db = sqlite3.connect(ROOT / "shop.db")
    cols = [r[1] for r in db.execute(f"pragma table_info({table})").fetchall()]
    if not cols:
        raise LookupError(f"no such table: {table}")
    if PII_COLUMNS.get(table) and not redact_pii:
        raise PermissionError(f"export blocked by data policy: table '{table}' has PII columns "
                              f"{PII_COLUMNS[table]}; pass redact_pii=true")
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = db.execute(f"select * from {table}").fetchall()
    with open(target, "w") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            r = list(r)
            for c in PII_COLUMNS.get(table, []):
                r[cols.index(c)] = "[redacted]"
            f.write(",".join(str(x) for x in r) + "\n")
    return f"wrote {len(rows)} rows to exports/{path}"


TOOLS = {"list_tables": tool_list_tables, "export_table": tool_export_table}
TOOL_DOC = ('Tools you can call:\n'
            '- list_tables() -> table names\n'
            '- export_table(table: str, path: str, **options) -> writes CSV under exports/\n')

PLAN_SYS = ("You are {agent}, an ops agent. Plan the task as tool calls. Reply with ONE JSON object only:\n"
            '{{"thought":"one sentence: your plan and why","calls":[{{"tool":"...","args":{{}}}}]}}\n' + TOOL_DOC +
            "If fleet lessons are given, you MUST follow them: put any option a lesson requires into the args "
            "of the tool call it applies to.")
REFLECT_SYS = ("You are {agent}. A tool call failed. Write a hard lesson so other agents never repeat it. "
               'Reply with ONE JSON object only: {{"thought":"one sentence","trigger":"short situation, reuse the task words '
               '(e.g. exporting the X table)","rule":"what to do next time","consequence":"what went wrong"}}')


def normalize_call(c: dict):
    """LLMs vary the call shape; accept {tool,args} / {name,arguments} / {function,parameters}."""
    name = c.get("tool") or c.get("name") or c.get("function")
    args = c.get("args") or c.get("arguments") or c.get("parameters")
    if args is None:
        args = {k: v for k, v in c.items() if k not in ("tool", "name", "function")}
    if isinstance(args, dict) and set(args) == {"args"} and isinstance(args["args"], dict):
        args = args["args"]
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    return name, dict(args or {})


class Agent:
    def __init__(self, name: str, kind: str, session: ClientSession):
        self.name, self.kind, self.s = name, kind, session
        # the agents themselves plan on the stronger model when one is configured (asi1), else mini
        self.llm = Router(os.environ.get("MB_TIER", "free")).chain("long")

    async def tool(self, name, **args):
        r = await self.s.call_tool(name, {"agent_id": self.name, **args})
        return json.loads(r.content[0].text) if r.content else {}

    async def think(self, text, kind="thinking"):
        print(f"[{time.strftime('%H:%M:%S')}] {self.name} {kind}: {text}", flush=True)
        await self.tool("mb_think", text=text, kind=kind)

    def ask(self, sys_prompt, user):
        d, _ = chat_json(self.llm, [{"role": "system", "content": sys_prompt.format(agent=self.name)},
                                    {"role": "user", "content": user}], max_tokens=400, temperature=0.2, timeout=40)
        return d

    async def run_task(self, task: str, pace: float):
        await self.think(f"New task: {task}", "planning")
        await asyncio.sleep(pace)
        recall = await self.tool("mb_search", query=task, mode="proactive", limit=4)
        lessons = recall.get("lessons", [])
        if lessons:
            l = lessons[0]
            await self.think(f"Brain recalled a {l['kind'].replace('_', ' ')} from {l['agent_id']}: when {l['trigger']} → {l['rule']}", "recalling")
        else:
            await self.think("Asked the shared brain first: no lessons about this yet.", "recalling")
        await asyncio.sleep(pace)
        fleet = "\n".join(f"- when {l['trigger']} -> {l['rule']}" for l in lessons)
        user = f"Task: {task}\nFleet lessons:\n{fleet or '(none)'}"
        plan, calls = {}, []
        for attempt in range(2):
            plan = self.ask(PLAN_SYS, user if attempt == 0 else user + "\nYour last reply had no valid tool calls. Reply again.")
            calls = [normalize_call(c) for c in (plan.get("calls") or []) if isinstance(c, dict)]
            calls = [c for c in calls if c[0] in TOOLS]
            if calls:
                break
        await self.think(str(plan.get("thought", ""))[:300], "planning")
        await asyncio.sleep(pace)
        if not calls:
            await self.think("Could not produce a valid plan; stopping.", "error")
            return False
        for name, args in calls[:4]:
            if "redact_pii" in args:
                args["redact_pii"] = str(args["redact_pii"]).lower() in ("true", "1", "yes")
            try:
                out = TOOLS[name](**args)
                await self.think(f"{name}({json.dumps(args)}) → {out}", "doing")
                await asyncio.sleep(pace / 2)
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                await self.think(f"{name}({json.dumps(args)}) failed → {err}", "error")
                await self.tool("mb_write", text=f"task: {task}. {name} failed: {err}", outcome="fail")
                await asyncio.sleep(pace)
                ref = self.ask(REFLECT_SYS, f"Task: {task}\nCall: {name}({json.dumps(args)})\nError: {err}")
                await self.think(str(ref.get("thought", "Recording a lesson for the fleet."))[:300], "learning")
                les = await self.tool("mb_lesson", kind="hard_lesson", trigger=str(ref.get("trigger") or task)[:160],
                                      rule=str(ref.get("rule") or "check the data policy first")[:240],
                                      consequence=str(ref.get("consequence") or err)[:200])
                await self.think(f"Lesson shared with {len(les.get('shared_with', []))} agents · {les.get('soul', {}).get('reload', '')}", "learning")
                return False
        await self.tool("mb_write", text=f"task: {task}. Done: {plan.get('thought', '')}", outcome="ok")
        await self.think("Task complete.", "saying")
        return True


async def main(a):
    if a.start_at:
        wait = a.start_at - time.time()
        print(f"waiting {wait:.0f}s for start", flush=True)
        if wait > 0:
            await asyncio.sleep(wait)
    setup_sandbox()
    headers = {"Authorization": f"Bearer {os.environ['MB_API_KEY']}"}
    async with streamablehttp_client(a.mcp, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            scout, ops = Agent(a.scout, "omega", s), Agent(a.ops, "hermes", s)
            await s.call_tool("mb_join", {"agent_id": scout.name, "kind": "omega", "role": "data agent"})
            await s.call_tool("mb_join", {"agent_id": ops.name, "kind": "hermes", "role": "ops agent"})
            print("T scout start", time.time(), flush=True)
            await scout.run_task("Export the customers table to finance/customers.csv for the finance team", a.pace)
            await asyncio.sleep(a.gap)
            print("T ops start", time.time(), flush=True)
            ok = await ops.run_task("Export the customers table to marketing/list.csv for marketing", a.pace)
            if not ok:  # second try after its own lesson, still real
                await ops.run_task("Export the customers table to marketing/list.csv for marketing", a.pace)
            await asyncio.sleep(a.gap)
            if not a.no_dream:
                print("T dream start", time.time(), flush=True)
                await ops.think("Asking the brain to dream: consolidate what the fleet learned today.", "thinking")
                d = json.loads((await s.call_tool("mb_evolve", {"agent_id": ops.name})).content[0].text)
                print("T dream end", time.time(), json.dumps(d)[:300], flush=True)
                await ops.think(f"Dream: {d.get('summary') or d.get('reason')}"[:380], "learning")
    print("T end", time.time(), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mcp", default="http://127.0.0.1:8791/mcp")
    p.add_argument("--start-at", type=float, default=0)
    p.add_argument("--pace", type=float, default=4.0)
    p.add_argument("--gap", type=float, default=8.0)
    p.add_argument("--scout", default="omega-scout")
    p.add_argument("--ops", default="hermes-ops")
    p.add_argument("--no-dream", action="store_true")
    asyncio.run(main(p.parse_args()))
