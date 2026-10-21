"""Optional mirror into Hy-Memory (vector + graph) for richer recall.

Enable with MB_BACKEND=hy. The brain_id is used as Hy-Memory's user_id so
every member agent writes into ONE memory space; agent_id is kept for
attribution. Best effort: failures never break the core path.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger("motherbrain.backends")


class HyMirror:
    def __init__(self, brain_id: str, mode: str = "pro"):
        from hy_memory import HyMemoryClient  # heavy import, only when enabled

        self.brain_id = brain_id
        self.client = HyMemoryClient(mode=os.environ.get("MB_HY_MODE", mode))

    def add(self, text: str, agent_id: str, scene: Optional[str]) -> None:
        try:
            self.client.add(text, user_id=self.brain_id, metadata={"agent_id": agent_id, "scene": scene})
        except TypeError:
            self.client.add(text, user_id=self.brain_id)
        except Exception as e:
            log.warning("hy mirror add failed: %s", e)

    def search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        try:
            res = self.client.search(query, user_ids=[self.brain_id])
        except Exception as e:
            log.warning("hy mirror search failed: %s", e)
            return []
        items = res if isinstance(res, list) else getattr(res, "results", None) or getattr(res, "memories", None) or []
        out = []
        for r in items[:limit]:
            text = r.get("memory") or r.get("text") if isinstance(r, dict) else getattr(r, "memory", None) or getattr(r, "text", "")
            if text:
                out.append({"text": str(text), "stage": "long", "kind": "fact", "agent_id": "hy-memory",
                            "score": 0.5, "source": "hy"})
        return out


def load(brain_id: str):
    if os.environ.get("MB_BACKEND", "").lower() not in ("hy", "hy-memory", "hymemory"):
        return None
    try:
        return HyMirror(brain_id)
    except Exception as e:
        log.warning("MB_BACKEND=hy but Hy-Memory failed to start: %s", e)
        return None
