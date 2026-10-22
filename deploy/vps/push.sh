#!/usr/bin/env bash
# Push the FLEET brain's snapshot to the owner dashboard (outbound only; no public route to the fleet brain).
#   ssh vps 'bash -s' < deploy/vps/push.sh
set -euo pipefail
grep -q '^MB_PUSH_SECRET=' /opt/motherbrain/.env || { echo "MB_PUSH_SECRET missing in /opt/motherbrain/.env"; exit 1; }
cat > /etc/systemd/system/motherbrain-push.service <<'UNIT'
[Unit]
Description=Motherbrain: push fleet snapshot to the owner dashboard
After=motherbrain.service network-online.target

[Service]
WorkingDirectory=/opt/motherbrain
EnvironmentFile=/opt/motherbrain/.env
ExecStart=/opt/motherbrain/.venv/bin/motherbrain push --url https://motherbrain.vercel.app/api/owner/ingest --every 10
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now motherbrain-push >/dev/null 2>&1
systemctl restart motherbrain-push
sleep 2; systemctl is-active motherbrain-push
