#!/usr/bin/env python3
"""Low-rate, allowlisted HTTP health checks for systems you administer."""
from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
import time
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlparse

import aiohttp
from aiohttp.abc import AbstractResolver
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

MAX_BODY_BYTES = 1024 * 1024
LOCAL_NAMES = {"localhost"}
LOCAL_IPS = {"127.0.0.1", "::1"}


def normalized_host(value: str) -> str:
    return value.strip().lower().rstrip(".")


def configured_allowlist() -> set[str]:
    values = {normalized_host(x) for x in os.getenv("SNCK_TEST_ALLOWLIST", "").split(",") if x.strip()}
    return values | LOCAL_NAMES | LOCAL_IPS


ALLOWED_HOSTS = configured_allowlist()


class SafeResolver(AbstractResolver):
    """Resolve only public IPs, except explicit loopback-only local testing."""

    async def resolve(self, host, port=0, family=socket.AF_UNSPEC):
        normalized = normalized_host(host)
        try:
            literal = ipaddress.ip_address(normalized)
        except ValueError:
            literal = None

        loop = asyncio.get_running_loop()
        if literal is not None:
            addresses = [(socket.AF_INET6 if literal.version == 6 else socket.AF_INET, str(literal))]
        else:
            infos = await loop.getaddrinfo(
                host, port, family=family, type=socket.SOCK_STREAM
            )
            addresses = list(dict.fromkeys((item[0], item[4][0]) for item in infos))

        if not addresses:
            raise OSError("Target host did not resolve")

        results = []
        for addr_family, address in addresses:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
            if normalized in LOCAL_NAMES | LOCAL_IPS:
                if not ip.is_loopback:
                    raise OSError("localhost resolved to a non-loopback address")
            elif not ip.is_global:
                raise OSError("Target resolves to a non-public or reserved IP address")
            results.append({
                "hostname": host,
                "host": str(ip),
                "port": port,
                "family": addr_family,
                "proto": socket.IPPROTO_TCP,
                "flags": 0,
            })
        return results

    async def close(self):
        return None


app = FastAPI(title="SNCK Command Center", docs_url=None, redoc_url=None)
state = {
    "running": False, "target": "", "method": "GET", "started": 0.0,
    "requests": 0, "ok": 0, "errors": 0, "bytes": 0,
    "last_ms": 0.0, "total_ms": 0.0, "workers": 0, "rate": 0,
}
history = deque(maxlen=50)
stop_event = asyncio.Event()
state_lock = asyncio.Lock()
schedule_lock = asyncio.Lock()
next_due = 0.0
task: asyncio.Task | None = None


class TestConfig(BaseModel):
    target: str = Field(min_length=8, max_length=2048)
    method: str = Field(default="GET", pattern="^(GET|HEAD)$")
    rate: int = Field(default=2, ge=1, le=10)
    workers: int = Field(default=2, ge=1, le=5)
    duration: int = Field(default=15, ge=1, le=60)


def snapshot():
    elapsed = max(time.monotonic() - state["started"], 0.001) if state["started"] else 0.001
    count = state["requests"]
    return {
        "running": state["running"], "target": state["target"],
        "requests": count,
        "success_rate": round(100 * state["ok"] / count, 1) if count else 0,
        "errors": state["errors"], "rps": round(count / elapsed, 2),
        "bandwidth_mbps": round(state["bytes"] * 8 / elapsed / 1_000_000, 4),
        "bytes_received": state["bytes"], "latency_ms": round(state["last_ms"], 1),
        "avg_latency_ms": round(state["total_ms"] / count, 1) if count else 0,
        "workers": state["workers"], "uptime": round(elapsed, 1) if state["started"] else 0,
    }


def validate_target(raw: str) -> str:
    try:
        parsed = urlparse(raw.strip())
        host = normalized_host(parsed.hostname or "")
        if parsed.scheme not in {"http", "https"} or not host:
            raise ValueError
        if parsed.username is not None or parsed.password is not None:
            raise ValueError
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if host not in ALLOWED_HOSTS:
            raise HTTPException(403, "Target host is not allowlisted. Set SNCK_TEST_ALLOWLIST to exact hosts you administer.")
        # Public hosts are restricted to standard web ports. Loopback may use a local dev port.
        if host not in LOCAL_NAMES | LOCAL_IPS and port not in {80, 443}:
            raise HTTPException(400, "Non-standard ports are allowed only for loopback testing.")
        return raw.strip()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "Enter a valid HTTP or HTTPS URL without embedded credentials.")


@app.get("/", response_class=HTMLResponse)
async def index():
    return PAGE


@app.get("/api/stats")
async def api_stats():
    return snapshot()


@app.get("/api/history")
async def api_history():
    return list(history)


@app.post("/api/start")
async def start(config: TestConfig):
    global task, next_due
    if state["running"] or (task is not None and not task.done()):
        raise HTTPException(409, "A test is already running.")
    target = validate_target(config.target)
    stop_event.clear()
    next_due = time.monotonic()

    async def run():
        global next_due
        state.update({
            "running": True, "target": target, "method": config.method,
            "started": time.monotonic(), "requests": 0, "ok": 0, "errors": 0,
            "bytes": 0, "last_ms": 0.0, "total_ms": 0.0,
            "workers": 0, "rate": config.rate,
        })
        deadline = time.monotonic() + config.duration
        max_requests = config.rate * config.duration
        scheduled_requests = 0
        connector = aiohttp.TCPConnector(
            limit=config.workers, ssl=True, resolver=SafeResolver(),
            use_dns_cache=False,
        )
        try:
            timeout = aiohttp.ClientTimeout(total=5, connect=2)
            async with aiohttp.ClientSession(
                timeout=timeout, connector=connector, trust_env=False,
                auto_decompress=True,
            ) as session:
                async def worker():
                    global next_due
                    nonlocal scheduled_requests
                    state["workers"] += 1
                    try:
                        while not stop_event.is_set() and time.monotonic() < deadline:
                            async with schedule_lock:
                                if scheduled_requests >= max_requests:
                                    break
                                scheduled_requests += 1
                                now = time.monotonic()
                                due = max(now, next_due)
                                next_due = due + 1 / config.rate
                            if due > now:
                                try:
                                    await asyncio.wait_for(stop_event.wait(), due - now)
                                    break
                                except asyncio.TimeoutError:
                                    pass
                            if stop_event.is_set() or time.monotonic() >= deadline:
                                break

                            started = time.monotonic()
                            received = 0
                            failed = False
                            try:
                                async with session.request(
                                    config.method, target, allow_redirects=False
                                ) as response:
                                    if config.method == "GET":
                                        async for chunk in response.content.iter_chunked(65536):
                                            received += len(chunk)
                                            if received > MAX_BODY_BYTES:
                                                failed = True
                                                break
                                    elapsed_ms = (time.monotonic() - started) * 1000
                                    state["requests"] += 1
                                    state["bytes"] += min(received, MAX_BODY_BYTES)
                                    state["last_ms"] = elapsed_ms
                                    state["total_ms"] += elapsed_ms
                                    if 200 <= response.status < 400 and not failed:
                                        state["ok"] += 1
                                    else:
                                        state["errors"] += 1
                            except Exception:
                                elapsed_ms = (time.monotonic() - started) * 1000
                                state["requests"] += 1
                                state["errors"] += 1
                                state["last_ms"] = elapsed_ms
                                state["total_ms"] += elapsed_ms
                    finally:
                        state["workers"] -= 1

                await asyncio.gather(*(worker() for _ in range(config.workers)))
        finally:
            state["running"] = False
            state["workers"] = 0
            result = snapshot()
            history.appendleft({
                "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "target": target, "duration": result["uptime"],
                "requests": result["requests"], "success_rate": result["success_rate"],
                "avg_latency_ms": result["avg_latency_ms"],
                "bandwidth_mbps": result["bandwidth_mbps"],
            })

    task = asyncio.create_task(run())
    return {"ok": True, "message": "Bounded health check started."}


@app.post("/api/stop")
async def stop():
    stop_event.set()
    current = task
    if current is not None and not current.done():
        try:
            await asyncio.wait_for(current, 6)
        except asyncio.TimeoutError:
            current.cancel()
    return {"ok": True}


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SNCK Command Center</title><style>
:root{color-scheme:dark;--bg:#070a0d;--panel:#10171d;--line:#263640;--muted:#91a4af;--mint:#67e6bf}*{box-sizing:border-box}body{margin:0;padding:24px;background:radial-gradient(ellipse at top,#12262b,#070a0d 65%);color:#edf5f7;font:14px ui-monospace,monospace}.wrap{max-width:1080px;margin:auto}header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.logo{color:var(--mint);border:1px solid #31574e;border-radius:9px;padding:13px;margin-right:10px}.brand{display:flex;align-items:center}.muted{color:var(--muted);font-size:11px;margin-top:5px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.panel{border:1px solid var(--line);background:#10171ded;border-radius:12px;padding:18px}.panel h2{font-size:11px;letter-spacing:.12em;color:var(--muted);margin:0 0 14px}.notice{grid-column:1/-1;border:1px solid #31594e;background:#0c211c;padding:12px;border-radius:9px;color:#b8f4df;font-size:12px;line-height:1.6}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:9px}.metric{background:#080e12;border:1px solid #1e2c34;border-radius:8px;padding:13px}.metric label{color:var(--muted);font-size:10px}.v{font-size:22px;margin-top:8px;font-weight:bold;overflow-wrap:anywhere}.mint{color:var(--mint)}label{display:block;color:var(--muted);font-size:11px;margin:12px 0 6px}input,select{width:100%;padding:10px;background:#080e12;color:#edf5f7;border:1px solid var(--line);border-radius:6px;font:inherit}.row,.actions{display:flex;gap:10px}.row>*{flex:1;min-width:0}.actions{margin-top:15px}button{flex:1;padding:12px;border:0;border-radius:6px;font:inherit;font-weight:bold;cursor:pointer}.go{background:var(--mint);color:#062019}.halt{background:#351d24;color:#ffb0b8}.history{grid-column:1/-1;overflow:auto}table{width:100%;border-collapse:collapse;font-size:11px}td,th{text-align:left;padding:10px;border-bottom:1px solid var(--line);white-space:nowrap}th{color:var(--muted)}@media(max-width:700px){body{padding:13px}.grid{grid-template-columns:1fr}.notice,.history{grid-column:auto}}</style></head><body><main class="wrap"><header><div class="brand"><div class="logo">S</div><div><b>SNCK COMMAND CENTER</b><div class="muted">AUTHORIZED HTTP HEALTH CHECKS · LIVE TELEMETRY</div></div></div><div id="pill" class="muted">● IDLE</div></header><div class="grid">
<div class="notice">Safe mode: exact-host allowlist, DNS checks against private/reserved addresses, verified TLS, GET/HEAD only, max 10 requests/sec, 5 workers and 60 seconds. Response bodies are capped at 1 MiB per request. Dashboard is localhost-only.</div>
<section class="panel"><h2>TEST CONFIGURATION</h2><form id="form"><label>Allowlisted target URL</label><input id="target" type="url" placeholder="http://127.0.0.1:8000/health" required><div class="row"><div><label>Method</label><select id="method"><option>GET</option><option>HEAD</option></select></div><div><label>Rate (max 10/s)</label><input id="rate" type="number" value="2" min="1" max="10"></div></div><div class="row"><div><label>Workers (max 5)</label><input id="workers" type="number" value="2" min="1" max="5"></div><div><label>Duration (max 60s)</label><input id="duration" type="number" value="15" min="1" max="60"></div></div><div class="actions"><button class="go" id="start">▶ START CHECK</button><button class="halt" id="stop" type="button">■ STOP</button></div><p class="muted">Set SNCK_TEST_ALLOWLIST to exact hostnames/IPs you administer. Public targets use ports 80/443 only. No redirects or proxy environment variables are used.</p></form></section>
<section class="panel"><h2>LIVE TELEMETRY</h2><div class="metrics"><div class="metric"><label>REQUEST RATE</label><div class="v mint" id="rps">0/s</div></div><div class="metric"><label>LATENCY LAST / AVG</label><div class="v" id="latency">— / — ms</div></div><div class="metric"><label>SUCCESS RATE</label><div class="v mint" id="success">0%</div></div><div class="metric"><label>BANDWIDTH</label><div class="v" id="bandwidth">0 Mbps</div></div><div class="metric"><label>REQUESTS / ERRORS</label><div class="v" id="requests">0 / 0</div></div><div class="metric"><label>WORKERS / UPTIME</label><div class="v" id="workersLive">0 / 0s</div></div></div></section>
<section class="panel history"><h2>TEST HISTORY</h2><table><thead><tr><th>TIME UTC</th><th>TARGET</th><th>DURATION</th><th>REQUESTS</th><th>SUCCESS</th><th>AVG LATENCY</th><th>BANDWIDTH</th></tr></thead><tbody id="history"><tr><td colspan="7">No tests yet.</td></tr></tbody></table></section></div></main><script>
const $=id=>document.getElementById(id);async function api(path,options={}){const response=await fetch(path,{headers:{"Content-Type":"application/json"},...options});const data=await response.json();if(!response.ok)throw Error(data.detail||"Request failed");return data}function esc(value){return String(value).replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]))}
async function refresh(){try{const s=await api("/api/stats");$("pill").textContent=s.running?"● RUNNING":"● IDLE";$("pill").style.color=s.running?"#67e6bf":"#91a4af";$("rps").textContent=s.rps+"/s";$("latency").textContent=s.latency_ms+" / "+s.avg_latency_ms+" ms";$("success").textContent=s.success_rate+"%";$("bandwidth").textContent=s.bandwidth_mbps+" Mbps";$("requests").textContent=s.requests+" / "+s.errors;$("workersLive").textContent=s.workers+" / "+s.uptime+"s";$("start").disabled=s.running;const rows=await api("/api/history");$("history").innerHTML=rows.length?rows.map(x=>"<tr><td>"+esc(x.time)+"</td><td>"+esc(x.target)+"</td><td>"+x.duration+"s</td><td>"+x.requests+"</td><td>"+x.success_rate+"%</td><td>"+x.avg_latency_ms+" ms</td><td>"+x.bandwidth_mbps+" Mbps</td></tr>").join(""):'<tr><td colspan="7">No tests yet.</td></tr>'}catch(error){}}
$("form").onsubmit=async event=>{event.preventDefault();try{await api("/api/start",{method:"POST",body:JSON.stringify({target:$("target").value,method:$("method").value,rate:+$("rate").value,workers:+$("workers").value,duration:+$("duration").value})});refresh()}catch(error){alert(error.message)}};$("stop").onclick=async()=>{try{await api("/api/stop",{method:"POST"});refresh()}catch(error){alert(error.message)}};setInterval(refresh,1000);refresh();
</script></body></html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, host=os.getenv("SNCK_BIND_HOST", "127.0.0.1"),
        port=int(os.getenv("SNCK_PORT", "6666")),
    )
