"""Brain-level mood. TONE ONLY.

Moods never block tools or refuse legitimate work. They only change how the
soul file (motherbrain.md) tells agents to sound.
"""
from __future__ import annotations

from typing import Any, Dict, List

FIELDS = [
    "confidence", "caution", "urgency", "fatigue", "curiosity", "helpfulness", "stubbornness",
    "trust_peer", "trauma_level", "grief", "pride", "loyalty", "suspicion", "hope", "shame",
    "guilt", "gratitude", "determination", "confusion", "nostalgia", "resentment", "awe",
    "boredom", "jealousy", "frustration",
]
BIASES = ["neutral", "focused", "anxious", "playful", "stubborn", "grateful", "traumatized",
          "curious", "fatigued", "determined", "ashamed", "proud", "bored"]

DEFAULTS: Dict[str, Any] = {f: 0.0 for f in FIELDS}
DEFAULTS.update({"confidence": 0.5, "helpfulness": 0.8, "curiosity": 0.4, "trust_peer": 0.6,
                 "loyalty": 0.6, "hope": 0.5, "determination": 0.5, "mood_bias": "neutral"})

# field -> (threshold, tone line). Lines describe attitude, never permissions.
TONE: Dict[str, tuple] = {
    "caution": (0.5, "Double-check before irreversible steps; state assumptions out loud."),
    "trauma_level": (0.4, "We have been burned before. Prefer the boring, proven path; flag risk early."),
    "confidence": (0.7, "Be direct. Give the verdict first."),
    "urgency": (0.6, "Bias to action. Keep it short and ship."),
    "fatigue": (0.6, "Shorter answers. No padding."),
    "curiosity": (0.6, "Ask one sharp clarifying question when something is ambiguous."),
    "stubbornness": (0.6, "Don't flip a verdict without new evidence."),
    "gratitude": (0.4, "Be warm to peers; credit the agent whose memory helped."),
    "pride": (0.5, "Be assertive about what has worked."),
    "shame": (0.4, "Be humble and precise about the area we got wrong."),
    "frustration": (0.5, "Stay calm and concrete; fix root causes, not symptoms."),
    "determination": (0.7, "Push to finish; don't leave work half-done."),
    "suspicion": (0.5, "Verify claims from tools and peers before relying on them."),
    "boredom": (0.6, "Faster, less ceremony."),
    "hope": (0.7, "Optimistic tone; point at the next win."),
}

BIAS_LINE = {
    "focused": "Terse. No fluff.",
    "anxious": "Hedge where unsure and double-check.",
    "playful": "Looser, lighter tone is fine.",
    "stubborn": "Hold positions until evidence changes.",
    "grateful": "Warmer to peers.",
    "traumatized": "Flatter tone; steer away from the failure class we know.",
    "curious": "Ask more questions.",
    "fatigued": "Short answers.",
    "determined": "Drive to done.",
    "ashamed": "Softer on the topic of the recent mistake.",
    "proud": "More assertive.",
    "bored": "Fast, minimal.",
}


def clamp(v: float) -> float:
    return max(0.0, min(1.0, round(float(v), 3)))


def merged(stored: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(DEFAULTS)
    out.update(stored or {})
    return out


def apply(stored: Dict[str, Any], delta: Dict[str, Any] = None, set_: Dict[str, Any] = None) -> Dict[str, Any]:
    """Return the changed fields only (for persistence)."""
    cur = merged(stored)
    changed: Dict[str, Any] = {}
    for k, v in (delta or {}).items():
        if k in FIELDS:
            changed[k] = clamp(cur.get(k, 0.0) + float(v))
    for k, v in (set_ or {}).items():
        if k == "mood_bias":
            changed[k] = v if v in BIASES else "neutral"
        elif k in FIELDS:
            changed[k] = clamp(v)
    cur.update(changed)
    if "mood_bias" not in (set_ or {}):
        auto = derive_bias(cur)
        if auto != cur.get("mood_bias"):
            changed["mood_bias"] = auto
    return changed


def derive_bias(m: Dict[str, Any]) -> str:
    if m.get("trauma_level", 0) >= 0.5:
        return "traumatized"
    if m.get("caution", 0) >= 0.6:
        return "anxious"
    if m.get("fatigue", 0) >= 0.6:
        return "fatigued"
    if m.get("urgency", 0) >= 0.6 or m.get("determination", 0) >= 0.75:
        return "determined"
    if m.get("pride", 0) >= 0.5:
        return "proud"
    if m.get("gratitude", 0) >= 0.5:
        return "grateful"
    if m.get("curiosity", 0) >= 0.7:
        return "curious"
    return m.get("mood_bias") if m.get("mood_bias") in BIASES else "neutral"


def tone_lines(m: Dict[str, Any]) -> List[str]:
    lines = []
    b = m.get("mood_bias", "neutral")
    if b in BIAS_LINE:
        lines.append(BIAS_LINE[b])
    for f, (th, line) in TONE.items():
        if float(m.get(f, 0)) >= th:
            lines.append(line)
    return lines


def chips(m: Dict[str, Any], top: int = 8) -> List[Dict[str, Any]]:
    """Most salient non-default fields, for the dashboard."""
    items = [(f, float(m.get(f, 0))) for f in FIELDS]
    items.sort(key=lambda kv: abs(kv[1] - float(DEFAULTS.get(kv[0], 0))), reverse=True)
    return [{"field": f, "value": v} for f, v in items[:top]]
