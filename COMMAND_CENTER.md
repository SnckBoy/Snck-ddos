# SNCK Command Center (safe mode)

Bounded HTTP/HTTPS health and load testing for systems you own or have explicit permission to test.

- Localhost bind by default at 127.0.0.1:6666.
- Exact host allowlist: loopback by default; add authorized hosts with SNCK_TEST_ALLOWLIST.
- GET/HEAD only, verified TLS, max 10 requests/sec, 5 workers and 60 seconds.
- Live request rate, latency, success rate, received bandwidth, workers, stop control and 50-entry history.
- No proxy rotation, IP spoofing, UDP/TCP floods, slow-client mode or amplification.

Install:
curl -fsSL https://raw.githubusercontent.com/SnckBoy/Snck-ddos/safe-command-center/install-command-center.sh | bash

Run:
cd ~/SNCK-Command-Center && source .venv/bin/activate && python command_center.py

Open http://127.0.0.1:6666 locally. For a remote VPS, use:
ssh -L 6666:127.0.0.1:6666 user@YOUR_VPS_IP

Allow specific hosts you administer by setting SNCK_TEST_ALLOWLIST to a comma-separated list of exact hostnames/IPs before launch. Keep the dashboard bound to localhost.
