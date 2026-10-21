"""Demo: agent fails -> lesson written -> a DIFFERENT agent doesn't fail again.

Runs offline (heuristic JEV) or online if MB_CUDOS_API_KEY is set.
"""
from __future__ import annotations

from .brain import Motherbrain


def _say(who: str, msg: str) -> None:
    print(f"  [{who}] {msg}")


def run(brain_id: str = "demo") -> Motherbrain:
    mb = Motherbrain(brain_id)
    print(f"\nMotherbrain demo · brain '{brain_id}' · tier {mb.tier}\n")
    mb.join("omega-1", kind="omega", role="deployer")
    mb.join("hermes-2", kind="hermes", role="ops")
    _say("motherbrain", "omega-1 and hermes-2 share one brain")

    task = "deploy the api to prod over rsync"
    print("\n1) omega-1 attempts the task with an empty brain")
    r = mb.search(task, agent_id="omega-1", mode="proactive")
    _say("omega-1", f"lessons before planning: {len(r['lessons'])}")
    mb.write(tool_trace={"tool": "rsync", "args": {"dest": "prod:/srv/api"},
                         "error": "ssh: connect to host prod port 22: Operation timed out (VPN down)"},
             agent_id="omega-1", outcome="fail", text=f"task: {task}")
    _say("omega-1", "FAILED: rsync timed out — VPN was down")

    print("\n2) omega-1 records a hard lesson for the whole fleet")
    l = mb.lesson(agent_id="omega-1", kind="hard_lesson", trigger="deploy to prod over rsync",
                  rule="bring up the VPN and check `nc -z prod 22` before rsync",
                  consequence="rsync timed out and the deploy failed")
    _say("motherbrain", f"lesson {l['lesson_id']} shared with {l['shared_with']}; {l['soul']['reload']}")

    print("\n3) hermes-2 (never saw the failure) gets the same task")
    r = mb.search(task, agent_id="hermes-2", mode="proactive")
    for les in r["lessons"]:
        _say("hermes-2", f"recalled from {les['agent_id']}: when {les['trigger']} -> {les['rule']}")
    mb.write(text=f"task: {task}. Checked VPN first (lesson from omega-1). Deploy succeeded.",
             agent_id="hermes-2", outcome="ok")
    _say("hermes-2", "OK: VPN checked first, deploy succeeded")

    print("\n4) dream state consolidates")
    d = mb.evolve(agent_id="hermes-2")
    _say("dream", d["summary"])

    ba = [b for b in mb.before_after() if b["lesson_id"] == l["lesson_id"]][0]
    print(f"\nBefore/after: fails before={ba['fails_before']} · lesson applied={ba['applied']}x · "
          f"fails after={ba['fails_after']} · ok after={ba['ok_after']} by {ba['ok_after_agents']}")
    print(f"Soul: {mb.soul.path}\n")
    return mb
