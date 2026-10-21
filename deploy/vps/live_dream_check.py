"""Live check of the stronger brain on the demo brain: dream + long-term write.
   ssh vps 'cd /opt/motherbrain && set -a && . ./.env.demo && set +a && .venv/bin/python -' < deploy/vps/live_dream_check.py
"""
import json, time
from motherbrain import Motherbrain

mb = Motherbrain()
t = time.time()
d = mb.evolve(agent_id="claude-4")
print(json.dumps({k: d[k] for k in ("summary", "promoted", "new_lessons", "merged", "brain_power", "tier")}, indent=1))
print("dream secs", round(time.time() - t, 1))
r = mb.write("Postmortem: the nightly backup cron wrote to a full disk for 3 days and nobody noticed; "
             "we lost the restore point. Fix: alert on disk >85% and verify each backup.", agent_id="hermes-3", outcome="fail")
print({k: r.get(k) for k in ("label", "priority", "jev")})
print("long:", mb.store.memories(mb.brain_id, stages=["long"], limit=1)[0]["text"])
