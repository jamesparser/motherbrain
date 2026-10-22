#!/usr/bin/env bash
# Load the Motherbrain plugin in a THROWAWAY Omega container (mock channel + mock provider,
# temp memory/workspace) to prove it loads before touching the live agent.
#   ssh vps 'bash -s' < plugins/motherbrain/omega/test-plugin-in-throwaway-container.sh
set -euo pipefail
OM=/opt/omega
IMG=$(docker inspect omega --format '{{.Config.Image}}')
T=$(mktemp -d /tmp/omega-mbtest.XXXX)
mkdir -p "$T/memory" "$T/workspace"
cp "$OM/memory/prompt.txt" "$T/memory/" 2>/dev/null || true
: > "$T/memory/history.metta"
docker exec omega cat /PeTTa/repos/Omega/config/plugins.yaml > "$T/plugins.yaml"
grep -q 'name: motherbrain' "$T/plugins.yaml" || printf -- '- name: motherbrain\n  loader: metta\n  location: "{REPO}/plugins/motherbrain"\n' >> "$T/plugins.yaml"
TOKEN=$(grep '^MB_API_KEY=' /opt/motherbrain/.env | cut -d= -f2-)
URL="http://$(tailscale ip -4 | head -1):8790"
docker rm -f omega-mbtest >/dev/null 2>&1 || true
mkdir -p "$T/plugin" && cp "$OM/plugins-motherbrain/"motherbrain.* "$T/plugin/" && printf '%s' "$TOKEN" > "$T/plugin/.token" && chmod 644 "$T/plugin/.token"
docker run -d -t -i --init --tmpfs /var/log/nginx:mode=1777 --name omega-mbtest --network omega_net --add-host host.docker.internal:172.26.0.1 \
  -v "$T/memory:/PeTTa/repos/Omega/memory" -v "$T/workspace:/workspace" \
  -v "$OM/proxy/nginx.conf.template:/opt/nginx/nginx.conf.template:ro" \
  -v "$OM/omega/config.yaml:/PeTTa/repos/Omega/config/config.yaml:ro" \
  -v "$OM/patches/providers.py:/PeTTa/repos/Omega/src/providers.py:ro" \
  -v "$T/plugin:/PeTTa/repos/Omega/plugins/motherbrain:ro" \
  -v "$T/plugins.yaml:/PeTTa/repos/Omega/config/plugins.yaml:ro" \
  "$IMG" config=/PeTTa/repos/Omega/config/config.yaml commchannel=test provider=Test \
  motherbrainEnabled=enabled motherbrainURL="$URL" motherbrainAgent=omega-mbtest >/dev/null
sleep "${WAIT:-45}"
docker logs omega-mbtest 2>&1 | grep -aE '\| (INFO|ERROR|WARNING) +\|' | grep -aiE 'motherbrain|Add skill: .*mb-|prompt extension motherbrain' | cut -c1-200 | head -20 || true
docker logs omega-mbtest > /tmp/mbtest.full.log 2>&1; docker rm -f omega-mbtest >/dev/null
rm -rf "$T"
