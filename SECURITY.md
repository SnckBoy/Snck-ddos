# Security and operational notes

## Scope

SNCK Command Center performs low-rate HTTP/HTTPS availability checks against exact hostnames or IP addresses configured by the operator. Use it only for systems you own or are explicitly authorized to monitor.

## Built-in limits

- GET and HEAD only
- Exact-host allowlist; no wildcard matching
- DNS results for non-local targets must all be globally routable
- Loopback targets must resolve only to loopback addresses
- Public targets use ports 80 or 443
- TLS certificate verification stays enabled
- Redirect following and environment proxy use are disabled
- At most 10 scheduled requests per second, 5 workers, and 60 seconds per run
- At most 1 MiB is consumed from each GET response
- Dashboard binds to loopback; use an SSH tunnel for remote access

## Deployment

Keep the dashboard on localhost. Do not set `SNCK_BIND_HOST` to a public interface, expose port 6666, or put the dashboard behind an unauthenticated public reverse proxy. Configure only exact target hosts in `SNCK_TEST_ALLOWLIST`.

## Reporting a vulnerability

Do not publish credentials, private target details, or exploit demonstrations in public issues. Contact the repository owner privately with a minimal reproduction and impact summary.
