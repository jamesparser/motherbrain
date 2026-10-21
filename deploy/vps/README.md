# Motherbrain on the Omega VPS

Host: the Omega VPS — `ssh vps` alias in ~/.ssh/config (Tailscale IP from `tailscale ip -4`).
Service: `motherbrain.service` → `motherbrain serve --host <tailscale-ip> --port 8790`.
Data: `/var/lib/motherbrain/brain.db` (SQLite) · soul: `/var/lib/motherbrain/brains/omega-fleet/motherbrain.md`.
Secrets: `/opt/motherbrain/.env` (600). Free tier uses the Omega Cudos key (`ASI_CUDOS_KEY_1`).

Bound to the tailnet IP only (ufw is inactive on this box, so 0.0.0.0 would be public).
`:8787` was already taken on the VPS, hence `:8790`.

```bash
# from the Mac, repo root
rsync -az --exclude __pycache__ motherbrain pyproject.toml README.md LICENSE assets vps:/opt/motherbrain/
ssh vps 'bash -s' < deploy/vps/install.sh            # install/update + restart
ssh vps 'cd /opt/motherbrain && set -a && . ./.env && set +a && .venv/bin/python -' < deploy/vps/smoke.py
ssh vps 'journalctl -u motherbrain -n 50 --no-pager'
```

Endpoints: `/mcp` (MCP streamable HTTP) · `/api/health` · `/api/snapshot` (dashboard) · `POST /api/tier` (admin key; Stripe webhook).

## Two brains on the VPS

| service | brain | bind | exposure |
|---|---|---|---|
| `motherbrain.service` | `omega-fleet` (real fleet) | tailnet IP :8790 | Tailscale only |
| `motherbrain-demo.service` | `bgi-demo` (seeded, judges) | 127.0.0.1:8791 | `https://motherbrain.realcryptocap.com` via cloudflared |

```bash
ssh vps 'bash -s' < deploy/vps/install-demo.sh                 # demo brain + seed
ssh vps 'bash -s' < deploy/vps/cloudflared-add-motherbrain.sh   # ingress rule on both connectors
```
DNS: `motherbrain` CNAME → `<tunnel-id>.cfargotunnel.com` (proxied) in the realcryptocap.com zone.
The Vercel dashboard reads the demo brain: `MB_API_URL=https://motherbrain.realcryptocap.com`, `MB_API_KEY` from `/opt/motherbrain/.env.demo`.
