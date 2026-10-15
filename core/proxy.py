# language: Python 3.11+, file: core/proxy.py
"""Proxy scrape + check — evolved from Kai Proxy checker."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Optional

import aiohttp

PROXY_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=5000&country=all",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=5000&country=all",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
]


async def scrape_proxies(timeout: float = 12.0) -> list[str]:
    found: set[str] = set()
    async with aiohttp.ClientSession() as session:
        for url in PROXY_SOURCES:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    text = await resp.text()
                    for line in text.splitlines():
                        line = line.strip()
                        if re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d+$", line):
                            found.add(line)
            except Exception:
                continue
    return sorted(found)


async def check_http(proxy: str, test_url: str = "http://httpbin.org/ip", timeout: float = 4.0) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                test_url,
                proxy=f"http://{proxy}",
                timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=False,
            ) as resp:
                return resp.status < 500
    except Exception:
        return False


async def check_batch(
    proxies: list[str],
    concurrency: int = 300,
    proxy_type: str = "http",
) -> list[str]:
    sem = asyncio.Semaphore(concurrency)
    live: list[str] = []

    async def _one(p: str) -> None:
        async with sem:
            ok = await check_http(p)
            if ok:
                live.append(p)

    await asyncio.gather(*[_one(p) for p in proxies], return_exceptions=True)
    return live


def load_proxies(path: str | Path) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        for prefix in ("http://", "https://", "socks4://", "socks5://"):
            if line.lower().startswith(prefix):
                line = line[len(prefix):]
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d+$", line):
            out.append(line)
    return out


def save_proxies(proxies: list[str], path: str | Path) -> None:
    Path(path).write_text("\n".join(proxies) + "\n", encoding="utf-8")
