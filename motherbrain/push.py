"""Push the brain's dashboard snapshot to the owner dashboard.

Outbound only: the private fleet brain never gets a public inbound route.
Sends only when the snapshot changed; auth = MB_PUSH_SECRET (Bearer).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import time
import urllib.request

from .brain import Motherbrain

log = logging.getLogger("motherbrain.push")


def run(url: str, every: float = 15.0) -> None:
    secret = os.environ["MB_PUSH_SECRET"]
    mb = Motherbrain()
    last = ""
    beat = 0.0
    while True:
        try:
            snap = mb.snapshot()
            body = json.dumps(snap, default=str, separators=(",", ":")).encode()
            h = hashlib.sha256(body).hexdigest()
            if h != last or time.time() - beat > 300:  # heartbeat every 5 min so "live" stays true
                req = urllib.request.Request(url, data=gzip.compress(body), method="POST", headers={
                    "Authorization": "Bearer " + secret, "Content-Type": "application/json",
                    "Content-Encoding": "gzip", "X-Pushed-At": str(int(time.time()))})
                with urllib.request.urlopen(req, timeout=20) as r:
                    r.read()
                last, beat = h, time.time()
        except Exception as e:
            log.warning("push failed: %s", e)
        time.sleep(every)
