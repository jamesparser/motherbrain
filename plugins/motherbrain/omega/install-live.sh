#!/usr/bin/env bash
# Enable the Motherbrain plugin on the LIVE Omega (compose). Backs up first; idempotent.
#   ssh vps 'bash -s' < plugins/motherbrain/omega/install-live.sh
# Rollback: ssh vps 'bash /opt/omega/backups/motherbrain-<ts>/rollback.sh'
set -euo pipefail
OM=/opt/omega
TS=$(date -u +%Y%m%dT%H%M%SZ)
BK=$OM/backups/motherbrain-$TS
mkdir -p "$BK"
cp -p "$OM/compose.yaml" "$BK/compose.yaml"
cp -p "$OM/omega/config.yaml" "$BK/config.yaml"
# memory snapshot (history + prompt; chroma is large, copied too if it fits)
tar -C "$OM" -czf "$BK/memory.tgz" memory 2>/dev/null || tar -C "$OM" -czf "$BK/memory.tgz" --exclude memory/chroma_db memory
docker inspect omega > "$BK/omega.inspect.json"
cat > "$BK/rollback.sh" <<RB
#!/usr/bin/env bash
set -e
cp -p "$BK/compose.yaml" "$OM/compose.yaml"
cd "$OM" && docker compose up -d omega
RB
chmod +x "$BK/rollback.sh"

# plugin files + token
mkdir -p "$OM/plugins-motherbrain"
grep '^MB_API_KEY=' /opt/motherbrain/.env | cut -d= -f2- | tr -d '\n' > "$OM/plugins-motherbrain/.token"
chmod 644 "$OM/plugins-motherbrain/.token"
[ -f "$OM/plugins-motherbrain/motherbrain.metta" ] || { echo "plugin files missing in $OM/plugins-motherbrain"; exit 1; }

# plugins.yaml = image default + motherbrain
docker exec omega cat /PeTTa/repos/Omega/config/plugins.yaml > "$OM/omega/plugins.yaml"
grep -q 'name: motherbrain' "$OM/omega/plugins.yaml" || printf -- '- name: motherbrain\n  loader: metta\n  location: "{REPO}/plugins/motherbrain"\n' >> "$OM/omega/plugins.yaml"

URL="http://$(tailscale ip -4 | head -1):8790"
python3 - "$OM/compose.yaml" "$URL" <<'PY'
import sys, yaml
path, url = sys.argv[1], sys.argv[2]
raw = open(path).read()
d = yaml.safe_load(raw)
s = d["services"]["omega"]
vols = s.setdefault("volumes", [])
# A freshly created container from this image cannot open /var/log/nginx (the old one had
# been fixed in place), so give nginx a writable tmpfs or the gateway crash-loops.
tm = s.setdefault("tmpfs", [])
if not any(str(x).startswith("/var/log/nginx") for x in tm):
    tm.append("/var/log/nginx:mode=1777")
for v in ("./plugins-motherbrain:/PeTTa/repos/Omega/plugins/motherbrain:ro",
          "./omega/plugins.yaml:/PeTTa/repos/Omega/config/plugins.yaml:ro"):
    if v not in vols:
        vols.append(v)
cmd = [c for c in s.get("command", []) if not c.startswith("motherbrain")]
cmd += ["motherbrainEnabled=enabled", f"motherbrainURL={url}", "motherbrainAgent=omega"]
s["command"] = cmd
# keep comments out of the way: write a clean YAML (original kept in the backup)
open(path, "w").write(yaml.safe_dump(d, sort_keys=False, default_flow_style=False))
print("compose updated")
PY
cd "$OM"
docker compose config -q
docker compose up -d omega
for i in $(seq 1 30); do
  sleep 3
  if docker logs --since 3m omega 2>&1 | grep -aq 'Plugin motherbrain is loaded'; then break; fi
done
docker logs --since 3m omega 2>&1 | grep -aE '\| (INFO|ERROR) +\|' | grep -aiE 'motherbrain|Add skill: .*mb-|Plugin .* (loaded|failed)' | cut -c1-180
docker ps --filter name=^omega$ --format '{{.Names}} {{.Status}}'
echo "backup: $BK"
