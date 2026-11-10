#!/usr/bin/env python3
"""Launch the bounded, allowlisted SNCK HTTP test dashboard."""
from __future__ import annotations
import os

def main() -> None:
    import uvicorn
    host = os.getenv("SNCK_BIND_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("Refusing non-loopback bind. Keep the dashboard local and use an SSH tunnel.")
    port = int(os.getenv("SNCK_PORT", "6666"))
    if not 1 <= port <= 65535:
        raise SystemExit("SNCK_PORT must be between 1 and 65535.")
    print(f"SNCK Command Center: http://127.0.0.1:{port}")
    print("Remote access: use an SSH tunnel; do not expose this dashboard publicly.")
    uvicorn.run("command_center:app", host=host, port=port, log_level="info", workers=1)

if __name__ == "__main__":
    main()
