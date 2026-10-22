#!/usr/bin/env bash
# Nightly dream (mb_evolve) for both brains via systemd timers. Idempotent.
#   ssh vps 'bash -s' < deploy/vps/dream-timers.sh
set -euo pipefail
cat > /usr/local/bin/motherbrain-dream <<'SH'
#!/usr/bin/env bash
# usage: motherbrain-dream <envfile> <url>
set -euo pipefail
KEY=$(grep '^MB_API_KEY=' "$1" | cut -d= -f2-)
curl -fsS -m 300 -X POST -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"agent_id":"dream-timer"}' "$2/api/tools/evolve" | head -c 600; echo
SH
chmod 755 /usr/local/bin/motherbrain-dream
TS=$(tailscale ip -4 | head -1)
mk() { # name envfile url oncalendar
  cat > /etc/systemd/system/$1.service <<UNIT
[Unit]
Description=Motherbrain dream ($1)
[Service]
Type=oneshot
ExecStart=/usr/local/bin/motherbrain-dream $2 $3
UNIT
  cat > /etc/systemd/system/$1.timer <<UNIT
[Unit]
Description=Motherbrain dream schedule ($1)
[Timer]
OnCalendar=$4
Persistent=true
RandomizedDelaySec=300
[Install]
WantedBy=timers.target
UNIT
}
# 03:20 Asia/Phnom_Penh = 20:20 UTC
mk motherbrain-dream-fleet /opt/motherbrain/.env "http://$TS:8790" "*-*-* 20:20:00 UTC"
mk motherbrain-dream-demo /opt/motherbrain/.env.demo "http://127.0.0.1:8791" "*-*-* 00/6:40:00 UTC"
systemctl daemon-reload
systemctl enable --now motherbrain-dream-fleet.timer motherbrain-dream-demo.timer >/dev/null
systemctl list-timers --no-pager | grep motherbrain-dream
