"""Minimal OpenAI-compatible client with stage fallback. No retries: we fall down the chain."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .router import Endpoint

log = logging.getLogger("motherbrain.llm")


class NoLLM(RuntimeError):
    """No usable endpoint answered. Callers must degrade gracefully (heuristics)."""


_clients: Dict[Tuple[str, str], Any] = {}


def _client(ep: Endpoint, timeout: float):
    from openai import OpenAI

    key = (ep.base_url, ep.api_key or "")
    c = _clients.get(key)
    if c is None:
        c = OpenAI(base_url=ep.base_url, api_key=ep.api_key, max_retries=0, timeout=timeout)
        _clients[key] = c
    return c


def chat(
    chain: List[Endpoint],
    messages: List[Dict[str, str]],
    *,
    max_tokens: int = 512,
    temperature: float = 0.2,
    timeout: float = 30.0,
) -> Tuple[str, Endpoint]:
    if not chain:
        raise NoLLM("no endpoint configured")
    last: Optional[Exception] = None
    for ep in chain:
        try:
            r = _client(ep, timeout).with_options(timeout=timeout).chat.completions.create(
                model=ep.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = (r.choices[0].message.content or "").strip()
            if text:
                return text, ep
        except Exception as e:  # network, auth, rate limit -> fall down the chain
            log.warning("llm %s/%s failed: %s", ep.power, ep.model, type(e).__name__)
            last = e
    raise NoLLM(str(last) if last else "empty responses")


_JSON_RE = re.compile(r"\{.*\}", re.S)


def parse_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    try:
        return json.loads(text)
    except Exception:
        m = _JSON_RE.search(text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        try:
            from json_repair import repair_json  # dependency of hy-memory

            v = json.loads(repair_json(text))
            if isinstance(v, dict):
                return v
        except Exception:
            pass
    raise ValueError("no JSON object in model output")


def chat_json(chain: List[Endpoint], messages, **kw) -> Tuple[Dict[str, Any], Endpoint]:
    text, ep = chat(chain, messages, **kw)
    return parse_json(text), ep
