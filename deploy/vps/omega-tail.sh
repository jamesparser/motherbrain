#!/usr/bin/env bash
# Stream the live Omega's history.metta into the FLEET brain (thought events + pins as memories).
#   ssh vps 'bash -s' < deploy/vps/omega-tail.sh
set -euo pipefail
cat > /etc/systemd/system/motherbrain-omega-tail.service <<'UNIT'
[Unit]
Description=Motherbrain: tail Omega history into the fleet brain
After=motherbrain.service

[Service]
WorkingDirectory=/opt/motherbrain
EnvironmentFile=/opt/motherbrain/.env
ExecStart=/opt/motherbrain/.venv/bin/motherbrain omega-tail --history /opt/omega/memory/history.metta --agent omega
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now motherbrain-omega-tail >/dev/null 2>&1
systemctl restart motherbrain-omega-tail
sleep 2; systemctl is-active motherbrain-omega-tail
