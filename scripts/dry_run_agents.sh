#!/usr/bin/env bash
# Rehearse scripts/live_agents.py against a throwaway brain on :8799 (never touches the demo brain).
cd /opt/motherbrain
fuser -k 8799/tcp >/dev/null 2>&1 || true
rm -rf /tmp/mbdry
set -a; . ./.env.demo; set +a
MB_HOME=/tmp/mbdry MB_BRAIN=dry MB_TIER="${TIER:-free}" MB_DREAM_MIN_INTERVAL=0 nohup .venv/bin/motherbrain serve --host 127.0.0.1 --port 8799 > /tmp/mbdry.log 2>&1 &
sleep 4
.venv/bin/python scripts/live_agents.py --mcp http://127.0.0.1:8799/mcp --pace "${PACE:-0.5}" --gap 1 ${DREAM:---no-dream} > /tmp/mbdryrun.log 2>&1
fuser -k 8799/tcp >/dev/null 2>&1 || true
