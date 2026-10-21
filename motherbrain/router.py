"""Stage -> model router.

Memory is staged like a human brain, not split into domains:

    short  (now / last N turns)          cheapest
    long   (facts, lessons, identity)    medium/strong
    dream  (consolidate / evolve)        strongest

Every route falls back to the mini brain, so Free never dead-ends.
Model names are deployment config (env), not product copy.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

STAGES = ("short", "long", "dream", "jev")
TIERS = ("free", "pro", "ultra")

CUDOS_BASE_URL = "https://inference.asicloud.cudos.org/v1"
ASI1_BASE_URL = "https://api.asi1.ai/v1"


@dataclass(frozen=True)
class Endpoint:
    power: str            # mini | medium | strong | strongest
    base_url: str
    model: str
    api_key: Optional[str]

    @property
    def usable(self) -> bool:
        return bool(self.api_key)

    def public(self) -> Dict[str, str]:
        """Safe-to-log view (never includes the key)."""
        return {"power": self.power, "model": self.model}


# tier -> stage -> power  (HANDOVER §2)
TIER_TABLE: Dict[str, Dict[str, str]] = {
    "free":  {"short": "mini", "long": "mini",   "dream": "mini",      "jev": "mini"},
    "pro":   {"short": "mini", "long": "strong", "dream": "strong",    "jev": "mini"},
    "ultra": {"short": "mini", "long": "medium", "dream": "strongest", "jev": "mini"},
}

POWER_ORDER = ["mini", "medium", "strong", "strongest"]


def _env(*names: str, default: Optional[str] = None) -> Optional[str]:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return default


def endpoint_for(power: str) -> Endpoint:
    """Resolve a power level to an endpoint from env.

    mini      -> Cudos asi1-mini (hosted free). MB_MINI_* overrides (BYO on Free).
    medium    -> MB_MEDIUM_*    (default ASI1 API)
    strong    -> MB_STRONG_*    (default ASI1 API)
    strongest -> MB_STRONGEST_* (default ASI1 API)
    """
    if power == "mini":
        return Endpoint(
            power="mini",
            base_url=_env("MB_MINI_BASE_URL", default=CUDOS_BASE_URL),
            model=_env("MB_MINI_MODEL", default="asi1-mini"),
            api_key=_env("MB_MINI_API_KEY", "MB_CUDOS_API_KEY", "CUDOS_API_KEY"),
        )
    p = power.upper()
    return Endpoint(
        power=power,
        base_url=_env(f"MB_{p}_BASE_URL", default=ASI1_BASE_URL),
        model=_env(f"MB_{p}_MODEL", default="asi1-mini"),
        api_key=_env(f"MB_{p}_API_KEY"),
    )


class Router:
    def __init__(self, tier: str = "free"):
        tier = (tier or "free").lower()
        if tier not in TIERS:
            raise ValueError(f"unknown tier {tier!r}; expected one of {TIERS}")
        self.tier = tier

    def power(self, stage: str) -> str:
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}; expected one of {STAGES}")
        return TIER_TABLE[self.tier][stage]

    def chain(self, stage: str) -> List[Endpoint]:
        """Endpoints to try in order: the stage's power, then weaker, ending at mini."""
        want = self.power(stage)
        idx = POWER_ORDER.index(want)
        out: List[Endpoint] = []
        for p in reversed(POWER_ORDER[: idx + 1]):
            ep = endpoint_for(p)
            if ep.usable and ep not in out:
                out.append(ep)
        return out

    def describe(self) -> Dict[str, Dict[str, object]]:
        return {
            s: {"power": self.power(s), "available": [e.power for e in self.chain(s)]}
            for s in STAGES
        }
