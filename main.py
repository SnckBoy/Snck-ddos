#!/usr/bin/env python3
"""Snck-ddos — web panel on port 6767."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PORT = int(os.environ.get("SNCK_PORT", "6767"))
HOST = os.environ.get("SNCK_HOST", "0.0.0.0")


def main() -> None:
    print(f"\n  Snck-ddos panel -> http://0.0.0.0:{PORT}")
    print(f"  Open:   http://YOUR_VPS_IP:{PORT}")
    print(f"  Health: http://YOUR_VPS_IP:{PORT}/health")
    print(f"  Firewall: sudo ufw allow {PORT}/tcp\n")
    from web.app import run

    run(host=HOST, port=PORT)


if __name__ == "__main__":
    main()
