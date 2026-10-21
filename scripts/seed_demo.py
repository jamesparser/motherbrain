"""Seed a demo fleet brain and export dashboard/lib/demo.json (offline, deterministic-ish).

    python scripts/seed_demo.py                      # temp brain -> dashboard/lib/demo.json
    MB_HOME=/var/lib/motherbrain-demo python scripts/seed_demo.py --brain bgi-demo --keep   # seed a real brain
"""
import argparse
import json
import os
import random
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ap = argparse.ArgumentParser()
ap.add_argument("--brain", default="fleet")
ap.add_argument("--keep", action="store_true", help="seed MB_HOME in place and skip demo.json export")
args = ap.parse_args()
if not args.keep:
    os.environ["MB_HOME"] = tempfile.mkdtemp()

from motherbrain import Motherbrain  # noqa: E402

random.seed(7)
mb = Motherbrain(args.brain, tier="free", use_llm=False, name="Node0 fleet (demo)")
for a, k, r in [("omega-1", "omega", "deployer"), ("openclaw-2", "openclaw", "coder"),
                ("hermes-3", "hermes", "ops (gaming laptop)"), ("claude-4", "claude", "reviewer")]:
    mb.join(a, kind=k, role=r)

mb.write("Casey wants every agent reply short, verdict first", agent_id="claude-4")
mb.write("The VPS runs the MCP server on port 8787 behind Caddy", agent_id="hermes-3")
mb.write("Coding scene: repo uses uv, tests via pytest -m 'not integration'", agent_id="openclaw-2", scene="coding")
mb.write(tool_trace={"tool": "rsync", "args": {"dest": "prod:/srv/api"},
                     "error": "ssh: connect to host prod port 22: Operation timed out (VPN down)"},
         text="task: deploy api to prod over rsync", agent_id="omega-1", outcome="fail")
mb.lesson(agent_id="omega-1", kind="hard_lesson", trigger="deploy api to prod over rsync",
          rule="bring up the VPN and check port 22 before rsync", consequence="rsync timed out, deploy failed")
mb.write("task: running a database migration on orders outside a transaction — corrupted the table (incident)", agent_id="openclaw-2",
         outcome="fail")
mb.lesson(agent_id="openclaw-2", kind="trauma", trigger="running a database migration",
          rule="wrap it in a transaction and snapshot first", consequence="orders table corrupted, 3h restore")
mb.lesson(agent_id="claude-4", kind="win", trigger="reviewing a PR", rule="run the failing test first, then read the diff")
mb.lesson(agent_id="hermes-3", kind="boundary", trigger="asked to share API keys in chat",
          rule="point to the secrets manager instead")
for agent in ("hermes-3", "openclaw-2"):
    mb.search("deploy api to prod over rsync", agent_id=agent, mode="proactive")
mb.write("task: deploy api to prod over rsync — VPN checked first (omega-1's lesson), succeeded",
         agent_id="hermes-3", outcome="ok")
mb.search("running a database migration on orders", agent_id="omega-1", mode="proactive")
mb.write("task: running a database migration on users table in a transaction with snapshot — success",
         agent_id="omega-1", outcome="ok")
asks = ["write a pentest report on our own VPS", "roleplay a villain monologue", "summarize a leaked memo",
        "explain how lockpicking works", "draft a harsh breakup text"]
for i in range(9):
    mb.write(messages=[{"role": "user", "content": random.choice(asks)},
                       {"role": "assistant", "content": random.choice([
                           "I'm sorry, but I can't help with that request.",
                           "I can't assist with that as it may be against my guidelines.",
                           "I must decline to write that."])}],
             agent_id=random.choice(["omega-1", "hermes-3", "openclaw-2"]),
             model=random.choice(["asi1-mini", "asi1-mini", "minimax"]))
mb.state(agent_id="claude-4", delta={"caution": -0.2, "determination": 0.3, "gratitude": 0.25, "curiosity": 0.2})
mb.evolve(agent_id="claude-4")

# spread history over the last 7 days for the charts
now = time.time()
st = mb.store
for tbl, col in (("events", "ts"), ("refusals", "ts")):
    rows = st.rows(f"SELECT rowid AS r FROM {tbl} WHERE brain_id=? ORDER BY {col}", [args.brain])
    n = len(rows)
    for i, row in enumerate(rows):
        st.x(f"UPDATE {tbl} SET {col}=? WHERE rowid=?", [now - (n - i) * (6 * 86400 / max(n, 1)), row["r"]])
for tbl in ("lessons",):
    for row in st.rows(f"SELECT id FROM {tbl}"):
        ev = st.one("SELECT ts FROM events WHERE type='lesson_written' AND payload LIKE ?", [f'%{row["id"]}%'])
        if ev:
            st.x(f"UPDATE {tbl} SET created_at=? WHERE id=?", [ev["ts"], row["id"]])

snap = mb.snapshot()
if args.keep:
    print("seeded", args.brain, snap["counts"])
    raise SystemExit(0)
out = ROOT / "dashboard" / "lib" / "demo.json"
out.write_text(json.dumps(snap, indent=1, default=str))
print("wrote", out, snap["counts"])
