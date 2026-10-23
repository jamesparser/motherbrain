#!/usr/bin/env bash
# Run on the Mac: record one live take. Recorder drives the dashboard; agents start on the VPS
# the moment the dashboard is on the thoughts panel (GO file).
set -euo pipefail
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
REPO=/Users/terminal/Developer/work/motherbrain
W=~/tmp/mbvideo; TAKE=$W/take-$(date +%H%M%S); mkdir -p "$TAKE"
cd "$W"
cp "$REPO/scripts/video/record.mjs" "$W/record.mjs"   # ESM resolves playwright next to the script
node "$W/record.mjs" --out "$TAKE" > "$TAKE/recorder.log" 2>&1 &
REC=$!
for i in $(seq 1 120); do [ -f "$TAKE/GO" ] && break; kill -0 $REC 2>/dev/null || { echo "recorder died"; exit 1; }; sleep 1; done
[ -f "$TAKE/GO" ] || { echo "recorder never reached the thoughts panel"; kill $REC; exit 1; }
ssh -o BatchMode=yes -o ClearAllForwardings=yes "${VPS:-vps-battlechan}" \
  'cd /opt/motherbrain && set -a && . ./.env.demo && set +a && nohup .venv/bin/python scripts/live_agents.py --pace 4 --gap 8 > /tmp/mb-take-agents.log 2>&1 &' < /dev/null
wait $REC || true
scp -q -o ClearAllForwardings=yes "${VPS:-vps-battlechan}":/tmp/mb-take-agents.log "$TAKE/agents.log" || true
echo "$TAKE" > $W/LAST_TAKE
