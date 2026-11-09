# Snck-ddos

Web control panel + multi-method L3/L4/L7 engine + optional C++ ultra L4 core.

**Only use on systems you own or have written permission to test.** Unauthorized use is illegal.

---

## Quick install (one command)

Installs **system packages + Python + git + g++ + venv + pip deps + firewall port** automatically:

```bash
curl -fsSL https://raw.githubusercontent.com/SnckBoy/Snck-ddos/main/install.sh | bash
```

Uses `sudo` when needed. Supports Debian/Ubuntu, Fedora/RHEL, CentOS, Arch, Alpine.

Then:

```bash
cd ~/Snck-ddos
source .venv/bin/activate
python main.py
```

Open **http://YOUR-IP:6767**  
Health: **http://YOUR-IP:6767/health**

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

Optional env:

```bash
export SNCK_PORT=6767
export SNCK_HOST=0.0.0.0
```

---

## Features

| Area | Detail |
|------|--------|
| Panel | FastAPI dark UI on **:6767** (embedded HTML, always serves) |
| L7 | GET POST HEAD STRESS SLOW PPS COOKIE RHEX DYN CFB OVH BYPASS GSB XMLRPC |
| L4 | UDP TCP SYN ACK CPS |
| L3 / Game | ICMP VSE MCBOT |
| C++ L4 | `cpp/snck_l4` + `snck_ultra.sh` multi-process (Gbps-class on 10G/20G) |
| Proxies | Public scrape + concurrent live check |
| Stats | Live RPS, Mbps, workers, errors |

---

## Ultra L4 (C++)

```bash
cd ~/Snck-ddos/cpp
bash build.sh
./snck_ultra.sh udp TARGET_IP PORT 4 64 60 1200
# method host port processes threads_per duration payload
```

---

## API

| Endpoint | Method | Body |
|----------|--------|------|
| `/health` | GET | alive + engine status |
| `/api/start` | POST | `{target, method, threads, duration, payload_size, use_proxies}` |
| `/api/stop` | POST | — |
| `/api/stats` | GET | live counters |
| `/api/scrape` | POST | background proxy scrape + check |
| `/api/proxies` | GET | raw / live counts |

---

## Project layout

```
Snck-ddos/
├── main.py                 # entry — panel :6767
├── install.sh              # full auto installer
├── requirements.txt
├── core/
│   ├── engine.py             # Python attack workers
│   ├── proxy.py
│   └── cpp_bridge.py
├── cpp/
│   ├── snck_l4.cpp           # ultra L4 core
│   ├── build.sh
│   └── snck_ultra.sh         # multi-process launcher
├── web/
│   ├── app.py                # FastAPI routes + embedded UI
│   └── templates/index.html  # legacy template (unused by default)
├── static/
├── proxies.txt
└── live_proxies.txt
```

---

## License

For authorized security testing and research only. You are responsible for compliance with local law.
