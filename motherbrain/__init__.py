"""Motherbrain — shared cognitive memory for agent fleets (Hy-Memory fork).

One brain, many agents. Stages: short-term -> long-term -> dream.

    from motherbrain import Motherbrain
    mb = Motherbrain(brain_id="fleet", tier="free")
    mb.join("omega-1", kind="omega")
    mb.write("Deploys to prod need the VPN up first", agent_id="omega-1")
    mb.search("how do I deploy?", agent_id="hermes-2")   # sees omega-1's memory
"""

from .brain import Motherbrain
from .router import Router, STAGES, TIERS

__all__ = ["Motherbrain", "Router", "STAGES", "TIERS"]
__version__ = "0.1.0"
