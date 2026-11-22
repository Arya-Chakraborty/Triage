# Triage backend

Project-local incident control plane. This tree owns CLI, ingest, watchers, Gemini agent, and the JSON/SSE API. The visual dashboard is served from `src/triage/web/static/` when present.

## Install

```sh
python -m pip install -e ".[dev]"
triage --help
```

## Setup

```sh
triage init                          # interactive
TRIAGE_NONINTERACTIVE=1 \
  TRIAGE_GEMINI_API_KEY=... \
  triage init                        # CI / tests
```

Writes `.triage.yaml` (no secrets) and `~/.triage/secrets` (mode 0600).

## Run

```sh
triage watch                         # daemon: watchers + ingest + agent + API on 127.0.0.1:8787
triage run --name api -- uvicorn app:app
triage ship                          # remote collector (spools to .triage/spool.jsonl if ingest is down)
triage status
triage event deploy.failed --sha abc --env prod
```

`POST /ingest` requires `Authorization: Bearer <INGEST_TOKEN>` and a 256KB body cap.

## Tests

```sh
pytest
```
