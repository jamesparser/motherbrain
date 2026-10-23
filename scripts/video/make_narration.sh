#!/usr/bin/env bash
# Run on the VPS: synthesize narration lines with the local Kokoro TTS (port 8880).
set -euo pipefail
OUT=${1:-/tmp/mb-narration}; mkdir -p "$OUT"
python3 - "$OUT" <<'PY'
import json, sys, urllib.request
out = sys.argv[1]
lines = json.load(open("/tmp/narration.json"))
for name, text in lines:
    req = urllib.request.Request("http://127.0.0.1:8880/v1/audio/speech", method="POST",
        data=json.dumps({"model": "kokoro", "input": text, "voice": "am_michael", "response_format": "wav", "speed": 1.05}).encode(),
        headers={"Content-Type": "application/json"})
    open(f"{out}/{name}.wav", "wb").write(urllib.request.urlopen(req, timeout=120).read())
    print(name)
PY
