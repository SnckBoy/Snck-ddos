# SNCK Command Center

A bounded HTTP/HTTPS availability and latency test dashboard for systems you own or are explicitly authorized to test.

This safe configuration supports GET and HEAD only, exact-host allowlisting, verified TLS, no redirects, a maximum of 10 requests/second, 5 workers, and 60 seconds per run. It does not provide packet floods, proxy rotation, amplification, or bypass features.

## Install

```bash
git clone --depth 1 --branch safe-hardening-2026 https://github.com/SnckBoy/Snck-ddos.git ~/SNCK-Command-Center
cd ~/SNCK-Command-Center
bash install.sh
```

The installer creates a virtual environment, does not delete existing directories, and does not open firewall ports.

## Run

```bash
cd ~/SNCK-Command-Center
source .venv/bin/activate
python main.py
```

Open the dashboard on the same machine at http://127.0.0.1:6666.

The server refuses non-loopback bind addresses. For remote administration, create an SSH tunnel from your client:

```bash
ssh -L 6666:127.0.0.1:6666 USER@YOUR_SERVER
```

Then open http://127.0.0.1:6666 on your client.

## Allow a test target

By default only localhost, 127.0.0.1, and ::1 are allowed. To add exact hosts that you administer, set the environment variable before starting:

```bash
export SNCK_TEST_ALLOWLIST="example.test,192.0.2.10"
python main.py
```

Use only exact hostnames/IP addresses for which you have permission. Avoid broad wildcards.

## Limits and telemetry

- Methods: GET, HEAD
- Rate: 1–10 requests/second
- Workers: 1–5
- Duration: 1–60 seconds
- Request timeout: 5 seconds
- TLS certificate verification enabled
- Redirects disabled
- Dashboard bound to loopback only
- Telemetry: request count, success rate, errors, latency, received bytes, and estimated bandwidth

These are application-level measurements, not a substitute for server-side monitoring or a professional load-testing plan.

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| SNCK_BIND_HOST | 127.0.0.1 | Loopback address only |
| SNCK_PORT | 6666 | Local dashboard port |
| SNCK_TEST_ALLOWLIST | localhost addresses | Comma-separated exact target hosts |
| SNCK_INSTALL_DIR | ~/SNCK-Command-Center | Installation directory |

## Responsible use

Only test systems you own or have explicit authorization to assess. This project is intentionally restricted to low-rate HTTP/HTTPS checks.
