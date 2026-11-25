"""Shared, loopback-only launcher for the SNCK dashboard."""
from __future__ import annotations

import os
from collections.abc import Mapping


def server_settings(environ: Mapping[str, str] | None = None) -> tuple[str, int]:
    """Return validated bind settings; never permit a public dashboard bind."""
    env = os.environ if environ is None else environ
    host = env.get("SNCK_BIND_HOST", "127.0.0.1").strip().lower()
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit(
            "Refusing non-loopback bind. Keep the dashboard local and use an SSH tunnel."
        )

    raw_port = env.get("SNCK_PORT", "6666")
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        raise SystemExit("SNCK_PORT must be an integer between 1 and 65535.") from None
    if not 1 <= port <= 65535:
        raise SystemExit("SNCK_PORT must be between 1 and 65535.")
    return host, port


def main() -> None:
    host, port = server_settings()
    import uvicorn

    print(f"SNCK Command Center: http://127.0.0.1:{port}")
    print("Remote access: use an SSH tunnel; do not expose this dashboard publicly.")
    uvicorn.run("command_center:app", host=host, port=port, log_level="info", workers=1)
