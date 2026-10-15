#!/usr/bin/env python3
# language: Python 3.11+, file: main.py, target: Linux / Windows
"""Snck-ddos entrypoint — web panel on port 6666."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.app import run


def main() -> None:
    print(
        r"""
   _____            __            __    __
  / ___/____  _____/ /__         / /___/ /___  _____
  \__ \/ __ \/ ___/ //_/ ______ / / __  / __ \/ ___/
 ___/ / / / / /__/ ,<   /_____// / /_/ / /_/ (__  )
/____/_/ /_/\___/_/|_|        /_/\__,_/\____/____/

  Snck-ddos  ·  panel → http://0.0.0.0:6666
"""
    )
    run(host="0.0.0.0", port=6666)


if __name__ == "__main__":
    main()
