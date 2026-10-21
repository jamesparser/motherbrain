#!/usr/bin/env bash
# Public judge demo brain: separate brain + DB, bound to 127.0.0.1:8791, exposed only via cloudflared.
# The private fleet brain (motherbrain.service, tailnet) is never exposed publicly.
#   ssh vps 'bash -s' < deploy/vps/install-demo.sh
set -euo pipefail
APP=/opt/motherbrain
ENVF=$APP/.env.demo
HOME_DIR=/var/lib/motherbrain-demo
mkdir -p "$HOME_DIR"
if [ ! -f "$ENVF" ]; then
  CUDOS=$(grep -E '^MB_CUDOS_API_KEY=' "$APP/.env" | cut -d= -f2-)
  umask 077
  cat > "$ENVF" <<ENV
MB_HOME=$HOME_DIR
MB_BRAIN=bgi-demo
MB_TIER=free
MB_CUDOS_API_KEY=${CUDOS}
MB_API_KEY=$(openssl rand -hex 24)
MB_ADMIN_KEY=$(openssl rand -hex 24)
MB_CORS_ORIGINS=*
ENV
fi
chmod 600 "$ENVF"
if [ ! -f "$HOME_DIR/brain.db" ]; then
  (cd "$APP" && set -a && . "$ENVF" && set +a && .venv/bin/python scripts/seed_demo.py --brain bgi-demo --keep)
fi
cat > /etc/systemd/system/motherbrain-demo.service <<UNIT
[Unit]
Description=Motherbrain public demo brain (judges)
After=network-online.target

[Service]
WorkingDirectory=$APP
EnvironmentFile=$ENVF
ExecStart=$APP/.venv/bin/motherbrain serve --host 127.0.0.1 --port 8791
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now motherbrain-demo >/dev/null 2>&1 || true
systemctl restart motherbrain-demo
sleep 3
systemctl is-active motherbrain-demo
curl -fsS http://127.0.0.1:8791/api/health && echo
