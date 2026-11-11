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
export SNCK_TEST_ALLOWLIST="status.yourdomain.com"
python main.py
```

Replace the sample hostname with a real hostname you administer. Non-local targets must resolve to public IP addresses and use port 80 or 443. Do not use wildcards or documentation/example IP ranges.

## Telemetry

The dashboard reports request count, success rate, errors, latency, received bytes, estimated bandwidth, worker count and a 50-run in-memory history. Metrics are application-level and do not replace server-side monitoring. History is reset when the process restarts.

## Tests

Run the safety regression suite locally:

```bash
python -m pip install -r requirements.txt pytest
python -m py_compile main.py command_center.py
pytest -q
```

GitHub Actions runs compilation and the regression suite on Python 3.11, 3.12 and 3.13 for pushes to the feature branches and pull requests to `main`.

## Security

See [SECURITY.md](SECURITY.md) for deployment boundaries and vulnerability reporting guidance.
