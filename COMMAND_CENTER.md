# SNCK Command Center

Low-rate HTTP/HTTPS health checks for systems you administer.

- Loopback-only dashboard at 127.0.0.1:6666.
- Exact-host allowlist.
- Non-local DNS results must be globally routable; private/reserved destinations are rejected.
- GET/HEAD only, verified TLS, redirects disabled, proxy environment ignored.
- Maximum 10 requests/sec, 5 workers, 60 seconds and 1 MiB response body per request.
- Public targets use ports 80/443; loopback may use a local development port.
- Live request rate, latency, success rate, received bandwidth, stop control and 50-entry history.

Install from the default branch:

```bash
git clone --depth 1 --branch main https://github.com/SnckBoy/Snck-ddos.git ~/SNCK-Command-Center
cd ~/SNCK-Command-Center
bash install.sh
```

Run:

```bash
cd ~/SNCK-Command-Center
source .venv/bin/activate
python main.py
```

For remote access, use an SSH tunnel:

```bash
ssh -L 6666:127.0.0.1:6666 user@YOUR_SERVER
```

Set SNCK_TEST_ALLOWLIST to a comma-separated list of exact authorized public hostnames/IPs before launch. Localhost and loopback are allowed by default.
