# Snck-ddos

High-volume stress / load-testing toolkit with a web control panel on **port 6666**.

Layer-7 methods (GET / POST / HEAD / STRESS / SLOW) with proxy rotation, plus Layer-4 UDP / TCP floods. Async workers + optional live proxy pool.

> **Use only on systems you own or have explicit written authorization to test.** Unauthorized use is illegal.

---

## Quick install (one command)

```bash
curl -fsSL https://raw.githubusercontent.com/SnckBoy/Snck-ddos/main/install.sh | bash
```

Then:

```bash
cd ~/Snck-ddos
source .venv/bin/activate
python main.py
```

Open **http://YOUR-IP:6666**

---

## Manual install

```bash
git clone https://github.com/SnckBoy/Snck-ddos.git
cd Snck-ddos
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## Features

| Area | Detail |
|------|--------|
| Panel | FastAPI + dark UI on `:6666` |
| L7 | GET, POST, HEAD, STRESS (large body), SLOW (slowloris-style) |
| L4 | UDP flood, TCP connection flood |
| Proxies | Scrape from public lists + concurrent live check |
| Engine | asyncio + uvloop, configurable threads / duration / payload |
| Stats | Live RPS, Mbps, workers, errors |

---

## Throughput notes

True multi-Gbps numbers require:

- High-bandwidth VPS / dedicated (10G+ NIC)
- Large live proxy pool (thousands of residential / datacenter)
- For pure L4: raw sockets / kernel bypass (AF_XDP, DPDK) or amplification reflectors — not shipped in this userland build
- Distributed workers across multiple machines pointing at the same target

This panel maximizes what a single strong Python process can push. Scale out horizontally for higher aggregates.

---

## API (panel)

| Endpoint | Method | Body |
|----------|--------|------|
| `/api/start` | POST | `{target, method, threads, duration, payload_size, use_proxies}` |
| `/api/stop` | POST | — |
| `/api/stats` | GET | live counters |
| `/api/scrape` | POST | background proxy scrape + check |
| `/api/proxies` | GET | raw / live counts |

---

## Project layout

```
Snck-ddos/
├── main.py              # entry — starts panel on 6666
├── install.sh           # one-cmd installer
├── requirements.txt
├── core/
│   ├── engine.py        # attack workers
│   └── proxy.py         # scrape + check
├── web/
│   ├── app.py           # FastAPI routes
│   └── templates/
│       └── index.html   # control panel
├── static/
├── proxies.txt
└── live_proxies.txt
```

---

## License

For authorized security testing and research only. You are responsible for compliance with local law.
