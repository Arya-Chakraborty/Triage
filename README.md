# Triage

Project-local incident control plane. Watch logs and processes, ingest events from this machine or remote collectors, open incidents, optionally auto-fix with Gemini, and operate from a local dashboard.

## Install

Python 3.11+.

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

Writes `.triage.yaml` (no secrets) and `~/.triage/secrets` (mode 0600). Copy `.triage.yaml.example` if you prefer to edit by hand.

Non-interactive / CI:

```sh
TRIAGE_NONINTERACTIVE=1 \
  TRIAGE_GEMINI_API_KEY=... \
  TRIAGE_INGEST_TOKEN=... \
  triage init
```

## Commands

```sh
triage watch                         # store, watchers, agent, ingest, dashboard
triage run --name api -- uvicorn app:app
triage ship                          # remote collector
triage status
triage event deploy.failed --sha abc --env prod
```

`triage watch` binds the dashboard at **http://127.0.0.1:8787** by default (`dashboard.host` / `dashboard.port` in `.triage.yaml`).

## Environment

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` / `TRIAGE_GEMINI_API_KEY` | Gemini key (init writes it to secrets) |
| `INGEST_TOKEN` / `TRIAGE_INGEST_TOKEN` | Bearer token for `POST /ingest` |
| `TRIAGE_SECRETS_PATH` | Override `~/.triage/secrets` |
| `TRIAGE_NONINTERACTIVE` | `1` to skip init prompts |
| `TRIAGE_ALERT_EMAIL` | Alert recipient at init |
| `TRIAGE_SMTP_HOST` / `PORT` / `USER` / `PASSWORD` | SMTP at init |
| `TRIAGE_DASHBOARD_HOST` / `PORT` | Bind address at init |

Runtime also reads `GEMINI_API_KEY`, `INGEST_TOKEN`, `SMTP_USER`, `SMTP_PASSWORD` from the secrets file or the environment.

## Security

- Default bind is **localhost**. Do not expose the dashboard to the public internet.
- `POST /ingest` requires `Authorization: Bearer <INGEST_TOKEN>` and a 256KB body cap.
- Secrets file is created mode **0600**. Keep it out of git (`.gitignore` covers `.triage/`, `.triage.yaml`, `secrets`, `spool.jsonl`).
- The agent **never git-pushes**. `git_commit` is off unless `agent.allow_git_commit: true`, and even then it only commits listed files inside the sandbox.
- Do not put API keys in `.triage.yaml`.

## Remote collectors

`triage ship` tails local logs, sends heartbeats, and optionally follows docker logs. It posts to `ship.ingest_url` and spools to `.triage/spool.jsonl` if the control plane is down.

The collector must reach the control plane over a path you trust:

- **Same machine:** `http://127.0.0.1:8787/ingest`
- **LAN:** bind `dashboard.host` to the LAN address (or `0.0.0.0` on a trusted network) and set `ship.ingest_url` to `http://<lan-ip>:8787/ingest`
- **Tailscale:** bind to the tailnet IP (or `0.0.0.0`) and use `http://<tailscale-ip>:8787/ingest`
- **VPS:** terminate TLS with a reverse proxy in front of `:8787`; collectors use `https://triage.example/ingest` with the same bearer token

The agent and dashboard stay on the control-plane host. Collectors never run tools.

## Tests

```sh
pytest
```
