"""motherbrain CLI.

    motherbrain mcp                      stdio MCP server
    motherbrain serve [--host --port]    HTTP: /mcp + /api/* (VPS)
    motherbrain soul                     print motherbrain.md
    motherbrain snapshot                 dashboard JSON
    motherbrain demo                     fail -> lesson -> doesn't fail again (offline OK)
    motherbrain tiers                    show stage -> model routing for this env
"""
from __future__ import annotations

import argparse
import json
import sys


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="motherbrain")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("mcp")
    s = sub.add_parser("serve")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8787)
    sub.add_parser("soul")
    sub.add_parser("snapshot")
    sub.add_parser("tiers")
    d = sub.add_parser("demo")
    d.add_argument("--brain", default="demo")
    a = p.parse_args(argv)

    if a.cmd == "mcp":
        from .mcp.server import main_stdio

        main_stdio()
    elif a.cmd == "serve":
        import uvicorn

        from .api import create_app

        uvicorn.run(create_app(a.host, a.port), host=a.host, port=a.port)
    elif a.cmd == "soul":
        from .brain import Motherbrain

        print(Motherbrain().reload()["soul"])
    elif a.cmd == "snapshot":
        from .brain import Motherbrain

        json.dump(Motherbrain().snapshot(), sys.stdout, indent=2, default=str)
    elif a.cmd == "tiers":
        from .router import TIERS, Router

        for t in TIERS:
            print(t, json.dumps(Router(t).describe()))
    elif a.cmd == "demo":
        from .demo import run

        run(a.brain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
