#!/usr/bin/env bash
# Install / update Motherbrain MCP + API on the Omega VPS. Idempotent.
#   rsync -az --exclude __pycache__ motherbrain pyproject.toml README.md LICENSE assets vps:/opt/motherbrain/
#   ssh vps 'bash -s' < deploy/vps/install.sh
set -euo pipefail
APP=/opt/motherbrain
PORT=${MB_PORT:-8790}
# Bind to the tailnet IP: reachable by fleet agents on Tailscale, not the public internet.
HOST=${MB_BIND:-$(tailscale ip -4 2>/dev/null | head -1)}
HOST=${HOST:-127.0.0.1}
cd "$APP"

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
# Core only: the heavy Hy-Memory deps (chromadb, kuzu, ...) are not needed unless MB_BACKEND=hy.
.venv/bin/pip install -q --no-deps -e .
.venv/bin/pip install -q "mcp>=1.9,<2" uvicorn starlette "openai>=1.40,<3" rank-bm25 json-repair pydantic python-dotenv

mkdir -p /var/lib/motherbrain
if [ ! -f "$APP/.env" ]; then
  CUDOS=$(grep -E '^ASI_CUDOS_KEY_1=' /opt/omega/.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' || true)
  umask 077
  cat > "$APP/.env" <<ENV
MB_HOME=/var/lib/motherbrain
MB_BRAIN=omega-fleet
MB_TIER=free
MB_CUDOS_API_KEY=${CUDOS}
MB_API_KEY=$(openssl rand -hex 24)
MB_ADMIN_KEY=$(openssl rand -hex 24)
MB_CORS_ORIGINS=*
# Pro/Ultra brains (leave unset until SNET/vendor OK; routes fall back to mini):
# MB_STRONG_BASE_URL=https://api.asi1.ai/v1
# MB_STRONG_MODEL=
# MB_STRONG_API_KEY=
ENV
fi
chmod 600 "$APP/.env"

cat > /etc/systemd/system/motherbrain.service <<UNIT
[Unit]
Description=Motherbrain shared brain (MCP + API)
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
WorkingDirectory=$APP
EnvironmentFile=$APP/.env
ExecStart=$APP/.venv/bin/motherbrain serve --host $HOST --port $PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now motherbrain >/dev/null 2>&1 || true
systemctl restart motherbrain
sleep 3
systemctl is-active motherbrain
curl -fsS "http://$HOST:$PORT/api/health" && echo
echo "MCP: http://$HOST:$PORT/mcp  (Bearer from $APP/.env MB_API_KEY)"
