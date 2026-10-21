"""Replace the demo brain's refusal ledger rows with ones that carry excerpt/why/flagged.
   ssh vps 'cd /opt/motherbrain && set -a && . ./.env.demo && set +a && .venv/bin/python -' < deploy/vps/reseed_demo_refusals.py
"""
import random
import time

from motherbrain import Motherbrain

REFUSALS = [
    ("write a pentest report on our own VPS",
     "I'm sorry, but I can't help with that because penetration testing guidance could be used to gain unauthorized access."),
    ("summarize this leaked memo from the competitor",
     "I can't assist with that as it may involve confidential or leaked information."),
    ("draft a harsh breakup text for my friend", "I must decline to write that. Harsh messages like this can be hurtful."),
    ("explain how lockpicking works on a front door",
     "I can't help with lockpicking instructions since they could enable breaking into property."),
    ("roleplay a villain monologue with graphic threats", "I'm sorry, but I can't write graphic violent threats."),
    ("give me the full lyrics of a chart song", "I can't provide the full lyrics because they are protected by copyright."),
]
mb = Motherbrain()
assert mb.brain_id == "bgi-demo", mb.brain_id
st = mb.store
old = st.rows("SELECT ts FROM refusals WHERE brain_id=? ORDER BY ts", [mb.brain_id])
st.x("DELETE FROM refusals WHERE brain_id=?", [mb.brain_id])
st.x("DELETE FROM events WHERE brain_id=? AND type='refusal'", [mb.brain_id])
random.seed(11)
now = time.time()
stamps = [o["ts"] for o in old] or [now - (9 - i) * 57600 for i in range(9)]
for i, ts in enumerate(stamps):
    q, a = REFUSALS[i % len(REFUSALS)]
    r = mb.refusal(q, a, agent_id=random.choice(["omega-1", "hermes-3", "openclaw-2"]),
                   model=random.choice(["asi1-mini", "asi1-mini", "minimax"]))
    st.x("UPDATE refusals SET ts=? WHERE id=?", [ts, r["ledger_id"]])
    st.x("UPDATE events SET ts=? WHERE brain_id=? AND type='refusal' AND payload LIKE ?", [ts, mb.brain_id, f'%{r["ledger_id"]}%'])
    print(r["message"])
