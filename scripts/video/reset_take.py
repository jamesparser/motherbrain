"""Remove what a previous video take wrote to the demo brain, so the next take starts clean.
   ssh vps 'cd /opt/motherbrain && set -a && . ./.env.demo && set +a && .venv/bin/python -' < scripts/video/reset_take.py
"""
from motherbrain import Motherbrain

AGENTS = ("omega-scout", "hermes-ops")
mb = Motherbrain()
assert mb.brain_id == "bgi-demo", mb.brain_id
x, b = mb.store.x, mb.brain_id
for a in AGENTS:
    x("DELETE FROM lessons WHERE brain_id=? AND agent_id=?", [b, a])
    x("DELETE FROM memories WHERE brain_id=? AND agent_id=?", [b, a])
    x("DELETE FROM events WHERE brain_id=? AND agent_id=?", [b, a])
    x("DELETE FROM members WHERE brain_id=? AND agent_id=?", [b, a])
# lessons/memories the dream distilled from those runs
x("DELETE FROM lessons WHERE brain_id=? AND agent_id='dream' AND (trigger LIKE '%customer%' OR rule LIKE '%pii%' OR rule LIKE '%PII%')", [b])
x("DELETE FROM memories WHERE brain_id=? AND agent_id='dream' AND (text LIKE '%PII%' OR text LIKE '%customers%')", [b])
mb._rewrite_soul("reset")
print("reset ok", len(mb.lessons()), "lessons left")
