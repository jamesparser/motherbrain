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

## Public judge access (demo brain only)
`/opt/motherbrain/.env.demo` also sets `MB_PUBLIC_KEY` (shown on the dashboard), `MB_PUBLIC_RPM=60`,
`MB_DREAM_MIN_INTERVAL=600` and `MB_ALLOWED_HOSTS=motherbrain.realcryptocap.com` (MCP Host check behind the tunnel).
Public key: rate-limited per IP and globally, 6 KB body cap, cannot change tier. The fleet brain has no public key.
Nightly dreams: `deploy/vps/dream-timers.sh` (fleet 03:20 Phnom Penh, demo every 6 h).

## TEMPORARY: judge demo brain runs Pro on the paid ASI1 key  ⚠️ revert after judging

Set 2026-10-21 for BGI judging. In `/opt/motherbrain/.env.demo` (marked `# TEMP-PRO`):
`MB_TIER=pro`, `MB_STRONG_BASE_URL=https://api.asi1.ai/v1`, `MB_STRONG_MODEL=asi1`, `MB_STRONG_API_KEY=<ASI1_API_KEY from /opt/omega/.env>`.
Short-term + JEV stay on Cudos `asi1-mini`; long-term + dream use `asi1`.

Revert:
```bash
ssh vps "sed -i '/^# TEMP-PRO/d;/^MB_STRONG_/d;s/^MB_TIER=pro/MB_TIER=free/' /opt/motherbrain/.env.demo && systemctl restart motherbrain-demo"
```
(The fleet brain `motherbrain.service` was never changed: still Free / mini.)

Stripe: test-mode Payment Link `STRIPE_PAYMENT_LINK` on Vercel (product "Motherbrain Pro", $5/agent/month).
No Stripe secret is on Vercel yet, so a payment does not auto-flip a brain's tier; add
`STRIPE_SECRET_KEY` + `STRIPE_PRICE_PRO` + `STRIPE_WEBHOOK_SECRET` for API checkout + webhook.
