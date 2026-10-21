#!/usr/bin/env bash
# Add motherbrain.realcryptocap.com -> 127.0.0.1:8791 (public demo brain) to BOTH connectors
# of the existing tunnel (they load-balance; each ingress must know the hostname). Backs up, validates,
# then restarts one connector at a time so the tunnel never drops to zero connectors.
set -euo pipefail
HOST=motherbrain.realcryptocap.com
TS=$(date -u +%Y%m%dT%H%M%SZ)
for f in /etc/cloudflared/freemium.yml /etc/cloudflared/tencent.yml; do
  grep -q "$HOST" "$f" && { echo "$f already has $HOST"; continue; }
  cp -p "$f" "$f.bak-motherbrain-$TS"
  python3 - "$f" "$HOST" <<'PY'
import sys
path, host = sys.argv[1], sys.argv[2]
lines = open(path).read().splitlines(keepends=True)
i = max(n for n, l in enumerate(lines) if "service: http_status:404" in l)
indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
rule = f"{indent}# Motherbrain public demo brain (BGI judges)\n{indent}- hostname: {host}\n{indent}  service: http://127.0.0.1:8791\n"
lines.insert(i, rule)
open(path, "w").write("".join(lines))
PY
  /usr/local/bin/cloudflared tunnel --config "$f" ingress validate
  /usr/local/bin/cloudflared tunnel --config "$f" ingress rule "https://$HOST/api/health"
done
systemctl restart cloudflared-tencent; sleep 6; systemctl is-active cloudflared-tencent
systemctl restart cloudflared-freemium; sleep 6; systemctl is-active cloudflared-freemium
curl -s -o /dev/null -w "freemium still up: %{http_code}\n" -m 10 https://freemium.realcryptocap.com/health || true
