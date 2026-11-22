# Triage

Triage is a project-local incident control plane. It watches processes, log files, health checks, and remote collectors, opens incidents when something fails, and can try to fix the code with Gemini. If a change needs a human, it writes a report and can email it.

The dashboard runs on the same daemon: overview, systems, terminals, events, incidents (including the Gemini transcript), and telemetry.

## Requirements

- Python 3.11+
- A Gemini API key for auto-fix (optional; without it, incidents still open and escalate)

## Install

```sh
python -m pip install -e ".[dev]"
# or
uv pip install -e ".[dev]"
triage --help
```

## Setup

```sh
triage init
```

This writes:

- `.triage.yaml` in the project (no secrets; safe to copy from `.triage.yaml.example`)
- `~/.triage/secrets` (mode 0600) with `GEMINI_API_KEY` and `INGEST_TOKEN`

Non-interactive:

```sh
TRIAGE_NONINTERACTIVE=1 \
  TRIAGE_GEMINI_API_KEY=... \
  TRIAGE_INGEST_TOKEN=... \
  triage init
```

## Run

```sh
triage watch                         # watchers, ingest, agent, dashboard
```

Dashboard: **http://127.0.0.1:8787** (override with `dashboard.host` / `dashboard.port`).

```sh
triage run --name api -- uvicorn app:app    # wrap a process; stdout/stderr become events
triage ship                                 # remote collector (logs, heartbeats)
triage status                               # open incidents and asset health
triage event deploy.failed --sha abc --env prod
```

Click **Agent** or **Open incidents** on the overview to jump to the incident list. Open an incident to watch the Gemini tool transcript live.

## Config

`.triage.yaml` controls the model, log tails, health URLs, SMTP, and agent limits (`max_rounds`, `auto_fix`, `sandbox_root`, `allow_git_commit`). Secrets stay in `~/.triage/secrets` or the environment.

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` / `TRIAGE_GEMINI_API_KEY` | Gemini key |
| `INGEST_TOKEN` / `TRIAGE_INGEST_TOKEN` | Bearer token for `POST /ingest` |
| `TRIAGE_SECRETS_PATH` | Override secrets file path |
| `TRIAGE_NONINTERACTIVE` | `1` skips init prompts |
| `TRIAGE_ALERT_EMAIL` | Alert recipient at init |
| `TRIAGE_SMTP_HOST` / `PORT` / `USER` / `PASSWORD` | SMTP at init |
| `TRIAGE_DASHBOARD_HOST` / `PORT` | Bind address at init |

## How it decides

An event becomes an incident on error/fatal, two consecutive health failures, a non-zero process exit, or `deploy.failed`. Duplicate fingerprints attach to the open incident instead of opening another.

The agent uses a **manual** Gemini tool loop (not automatic function calling): read/grep/write files, limited shell, git status/diff, restart processes Triage started, then escalate. It never `git push`. `git_commit` is off unless you set `agent.allow_git_commit: true`.

Escalation always writes `.triage/reports/incident-<id>.md`. Email is sent only if SMTP is configured.

## Remote collectors

`triage ship` tails logs, sends heartbeats, and optionally follows docker logs. It posts to `ship.ingest_url` and spools to `.triage/spool.jsonl` if the control plane is down.

The collector must reach the daemon:

- Same machine: `http://127.0.0.1:8787/ingest`
- LAN / Tailscale: bind `dashboard.host` accordingly and point `ship.ingest_url` at that address
- Public host: put TLS on a reverse proxy in front of `:8787`

Collectors never run agent tools. Tools run only on the control plane, inside `sandbox_root`.

## Security

- Default bind is localhost. Do not expose the dashboard to the public internet without a proxy and auth you trust.
- `POST /ingest` requires `Authorization: Bearer <INGEST_TOKEN>` (256KB body cap).
- File tools cannot leave `sandbox_root`. Shell has a denylist (`rm -rf`, `sudo`, force-push, and similar).
- Secrets are redacted before they go to Gemini. Do not put API keys in `.triage.yaml`.

## Tests

```sh
pytest
```
