# SNCK Command Center

A bounded HTTP/HTTPS health-check dashboard for systems you own or are explicitly authorized to test.

## Safety controls

- GET and HEAD only; exact-host allowlist
- DNS resolution rejects private, loopback, link-local, multicast and reserved IPs for non-local targets
- Loopback is allowed for local development; public targets are restricted to ports 80 and 443
- TLS certificate verification enabled; redirects disabled; environment proxy settings ignored
- Maximum 10 requests/second, 5 workers, 60 seconds per run
- Maximum 1 MiB response body per request; 5-second request timeout
- Dashboard binds to loopback only; use an SSH tunnel for remote access
- No packet flooding, proxy rotation, amplification, spoofing or bypass functions

## Install

```bash
git clone --depth 1 --branch main https://github.com/SnckBoy/Snck-ddos.git ~/SNCK-Command-Center
cd ~/SNCK-Command-Center
bash install.sh
```

The installer does not delete existing directories or open firewall ports.

## Run

```bash
cd ~/SNCK-Command-Center
source .venv/bin/activate
python main.py
```

Open http://127.0.0.1:6666 on the same machine. For remote administration, create an SSH tunnel from your client:

```bash
ssh -L 6666:127.0.0.1:6666 USER@YOUR_SERVER
```

Then open http://127.0.0.1:6666 on your client.

## Allow an authorized target

The default allowlist contains localhost and loopback IPs. To add exact hostnames or public IPs that you administer:

```bash
export SNCK_TEST_ALLOWLIST="status.example.com,203.0.113.10"
python main.py
```

Replace the sample values with your own authorized public hostnames/IPs. Non-local targets must resolve to public IP addresses and use port 80 or 443. Do not use wildcards.

## Telemetry

The dashboard reports request count, success rate, errors, latency, received bytes, estimated bandwidth, worker count and a 50-run history. Metrics are application-level and do not replace server-side monitoring.
