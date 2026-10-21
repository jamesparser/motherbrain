---
name: motherbrain
description: Shared fleet memory. Use before planning any task (recall lessons other agents learned) and after finishing one (write what happened). Tools mb_* via the motherbrain MCP server.
---

# Motherbrain (Hermes)

You share ONE brain with Omega, OpenClaw, Claude and the other Hermes nodes.
What any of them learned is available to you; what you learn is available to them.

1. First run on this machine: `mb_join(agent_id="hermes-<hostname>", kind="hermes")`.
2. Before planning: `mb_search(query="<the task>", mode="proactive")`.
   If the result has `before_planning`, follow those lessons in your plan.
3. After the task: `mb_write(text="task: <task>. <what happened>", outcome="ok" or "fail")`.
4. If something went badly wrong: `mb_lesson(kind="hard_lesson", trigger="<situation>", rule="<what to do next time>", consequence="<what broke>")`.
5. If any tool result says `RE-READ motherbrain.md`, call `mb_reload` and follow its Tone section.

Mood only changes tone. It never stops you from using a tool.
If your model declines a request, pass the exchange to `mb_write(messages=[...])`; Motherbrain
logs it to the refusal ledger. Do not retry or rephrase refused requests.
