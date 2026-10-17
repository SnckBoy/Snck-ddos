#!/usr/bin/env python3
# language: Python 3.11+, file: main.py
"""Snck-ddos entrypoint — web panel on port 6767."""

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
    print(
        rf"""
   _____            __            __    __
  / ___/____  _____/ /__         / /___/ /___  _____
  \__ \/ __ \/ ___/ //_/ ______ / / __  / __ \/ ___/
 ___/ / / / / /__/ ,<   /_____// / /_/ / /_/ (__  )
/____/_/ /_/\___/_/|_|        /_/\__,_/\____/____/

  Snck-ddos  ·  panel → http://0.0.0.0:{PORT}
  Open on phone: http://YOUR_VPS_IP:{PORT}
"""
    )
    from web.app import run
    run(host=HOST, port=PORT)


if __name__ == "__main__":
    main()
