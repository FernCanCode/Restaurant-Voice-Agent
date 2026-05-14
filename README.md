# Restaurant Voice Ordering Agent

## Description

The Restaurant Voice Ordering Agent is a phone-capable, MCP-enabled, RAG-grounded restaurant voice ordering agent.

The official grading and reproduction path is Docker Compose. Docker is required for the supported run flow, and graders should not create a local Python virtual environment manually. The project image uses Python 3.11 through the Dockerfile.

It shall:
- greet restaurant callers
- answer menu questions using retrieved menu evidence
- handle dietary/allergen questions cautiously
- add, remove, and update order items
- support modifications and special instructions
- track running totals
- collect customer name
- read back the order
- confirm or cancel the order

The primary production interface is Twilio Programmable Voice and the local browser voice interface is the reproducible walkthrough and fallback interface.

## Technology Stack

- Python 3.11
- FastAPI
- Uvicorn
- Pydantic
- Anthropic Claude Haiku, default model `claude-haiku-4-5`
- MCP tool layer
- sentence-transformers
- `sentence-transformers/all-MiniLM-L6-v2`
- rapidfuzz
- NumPy
- Twilio Programmable Voice
- Browser Web Speech API
- pytest
- pytest-cov
- ruff
- black
- mypy
- pip-audit
- Locust
- Docker and Docker Compose

## Quick Start

Docker Compose is the only official grading/reproduction run path. Do not use a local Python virtual environment or direct Uvicorn run for grading. `.env` must never be committed, and `.env.example` contains placeholders only.

### 1. Clone And Enter The Repo

```bash
git clone https://github.com/FernCanCode/Restaurant-Voice-Agent
cd Restaurant-Voice-Agent
cp .env.example .env
```

### 2. Choose Exactly One Verification Mode

#### Mode A — Basic Docker Health/Readiness Check

Use this mode if you only want to verify that the container starts and the local app is reachable.

Required `.env` edits:
- None. Leave placeholder values as-is.

Run:

```bash
docker compose up --build
```

Verify:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
curl -s http://localhost:8000/voice/config-check
```

Expected result:
- `/health` returns status ok.
- `/ready` returns ready components or degraded status as documented.
- `/voice/config-check` is expected to show Twilio disabled or unconfigured.
- Missing Twilio fields are expected in Mode A and are not a failure for this basic verification mode.
- Browser fallback opens at `http://localhost:8000`.

Browser fallback UI:

```text
http://localhost:8000
```

The browser UI is a fallback/walkthrough aid. The Twilio phone path is the primary voice path.

#### Mode B — Full Twilio Phone + Anthropic Verification

Use this mode if you want to reproduce the real phone smoke test.

Before running Docker:
1. Start ngrok or cloudflared for local port `8000` and copy the public HTTPS base URL.
2. Edit `.env` and set these required fields:
- `ANTHROPIC_API_KEY=<your Anthropic API key>`
- `ANTHROPIC_MODEL=claude-haiku-4-5`
- `ENABLE_TWILIO=true`
- `TWILIO_ACCOUNT_SID=<your Twilio Account SID>`
- `TWILIO_AUTH_TOKEN=<your Twilio Auth Token>`
- `TWILIO_PHONE_NUMBER=<your Twilio phone number>`
- `TWILIO_WEBHOOK_BASE_URL=<your public HTTPS tunnel URL>`

Then run:

```bash
docker compose up --build
```

Then configure Twilio using that same public base URL:
- Voice webhook: `POST <PUBLIC_BASE_URL>/voice/incoming`
- Status callback: `POST <PUBLIC_BASE_URL>/voice/status`

If `.env` is changed after Docker is already running, restart the app:

```bash
docker compose down
docker compose up --build
```

Then verify:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
curl -s http://localhost:8000/voice/config-check
```

Expected result:
- `/voice/config-check` shows enabled/configured true with no missing fields.
- A real Twilio call can follow the script documented in `reports/phone_smoke_test.md`.

## Architecture Summary

- Twilio phone calls and browser voice turns both route into the same FastAPI backend.
- Both paths use the same shared agent orchestrator.
- The agent uses Anthropic Claude Haiku for language understanding and tool-routing proposals.
- MCP tools perform deterministic menu lookup, dietary lookup, order mutation, total calculation, confirmation, and cancellation.
- RAG retrieves grounded menu evidence from canonical menu JSON and local index files.
- The LLM does not compute totals or mutate order state.

Architecture diagrams and specification:
- [docs/SPEC.md](docs/SPEC.md)
- [docs/diagrams/architecture.svg](docs/diagrams/architecture.svg)
- [docs/diagrams/architecture.mmd](docs/diagrams/architecture.mmd)

## Voice Interfaces

### Production phone path

Routes:
- `POST /voice/incoming`
- `POST /voice/turn`
- `POST /voice/status`
- `GET /voice/config-check`

Requires Twilio credentials and a public webhook URL.

### Local browser voice path

Routes:
- `GET /`
- `GET /ui`
- `POST /api/browser/start-call`
- `POST /api/browser/voice-turn`

Used for local reproducible walkthroughs and does not require Twilio credentials.

### Shared API Routes

Routes:
- `GET /health`
- `GET /ready`
- `GET /api/status`
- `POST /api/sessions`
- `POST /api/turn`
- `GET /api/sessions/{session_id}`
- `GET /api/sessions/{session_id}/order`
- `POST /api/sessions/{session_id}/readback`
- `POST /api/sessions/{session_id}/confirm`
- `POST /api/sessions/{session_id}/cancel`
- `POST /api/menu/ingest-text`
- `POST /api/menu/ingest-url`
- `POST /api/menu/ingest-file`
- `POST /api/menu/rebuild-index`
- `GET /api/menu/items`
- `GET /api/menu/items/{item_id}`
- `POST /api/menu/search`
- `GET /api/logging/example`
- `GET /api/debug/sessions/recent`
- `GET /api/debug/session/{session_id}`

## API Dependencies

For a complete list of dependencies, see:
```text
api_dependencies.yaml
```

Dependencies:
- Anthropic Claude API
- Twilio Programmable Voice
- Browser Web Speech API
- Hugging Face / sentence-transformers model download

- No personal API keys are committed.
- All keys are read from `.env`.
- The TA/professor supplies their own keys when needed.

## Environment Configuration

Configuration template:
```text
.env.example
```

Important variables:
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `ENABLE_TWILIO`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`
- `TWILIO_WEBHOOK_BASE_URL`
- `ENABLE_BROWSER_VOICE`
- `MENU_RAW_FIXTURE_PATH`
- `MENU_DATA_PATH`
- `MENU_INDEX_PATH`
- `HF_HOME`
- `TRANSFORMERS_CACHE`
- `ENABLE_DEBUG_ROUTES`

- Twilio credentials are required when `ENABLE_TWILIO=true`.
- `ANTHROPIC_API_KEY` is required for full Anthropic LLM behavior.
- Browser walkthrough does not require Twilio.
- Missing Anthropic should trigger degraded LLM mode for simple supported flows.
- `.env.example` contains placeholders only.
- Placeholder values are acceptable for no-secret local health checks.
- `.env` must not be committed.
- `/voice/config-check` reports missing Twilio fields without exposing secrets.

## Running the App

Official grading/reproduction path:

```bash
docker compose up --build
```

Expected:
- app listens on `http://localhost:8000`
- `/health` works
- `/ready` works
- `/voice/config-check` shows Twilio enabled/configured status without secrets
- browser voice UI loads
- Twilio routes are registered
- the container uses Python 3.11 from the Dockerfile

## Health and Readiness Checks

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
curl -s http://localhost:8000/voice/config-check
```

- `/health`: Checks if the service is alive and responding.
- `/ready`: Reports menu, RAG, MCP, Anthropic, Twilio, browser voice, and degraded-mode status.
- `/voice/config-check`: Confirms whether Twilio is enabled/configured and lists missing fields without exposing secrets.

## Twilio Phone Runbook

For a real phone test:

1. Start ngrok or cloudflared for local port `8000` and copy the public HTTPS base URL.
2. Edit `.env` and set:
   - `ANTHROPIC_API_KEY`
   - `ANTHROPIC_MODEL=claude-haiku-4-5`
   - `ENABLE_TWILIO=true`
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_PHONE_NUMBER`
   - `TWILIO_WEBHOOK_BASE_URL=<PUBLIC_BASE_URL>`
3. Do not commit `.env`.
4. Start the app with `docker compose up --build`.
5. If `.env` was changed after Docker was already running, restart with:
   - `docker compose down`
   - `docker compose up --build`
6. Verify:
   - `curl -s http://localhost:8000/health`
   - `curl -s http://localhost:8000/ready`
   - `curl -s http://localhost:8000/voice/config-check`
   - `curl -s <PUBLIC_BASE_URL>/health`
   - `curl -s <PUBLIC_BASE_URL>/voice/config-check`
7. In the Twilio Console, configure the phone number voice webhook as:
   - `POST <PUBLIC_BASE_URL>/voice/incoming`
8. Optional status callback:
   - `POST <PUBLIC_BASE_URL>/voice/status`
9. Call the Twilio number from a real phone.
10. After the call, inspect:
   - `GET /api/debug/sessions/recent`
   - `GET /api/debug/session/{session_id}`
   - logs correlated by `twilio_call_sid`, `session_id`, or `request_id`

## Browser Fallback

Open:

```text
http://localhost:8000
```

Use the browser UI for walkthrough and fallback verification only. It is not the main phone interface.

## Results

- Final preflight status: passed
- Latest automated validation count: `264 passed`
- Twilio phone smoke test: passed
  - Reference: `reports/phone_smoke_test.md`
- Browser walkthrough screenshots: captured for `US-01` through `US-10`
  - Reference: `reports/walkthrough.md`
- `pip-audit` note: it could not complete in the local sandbox because DNS resolution to `pypi.org` was unavailable
  - Reference: `reports/security.txt`

## TA Grading Checklist

1. Start the app with Docker Compose:

```bash
docker compose up --build
```

2. Verify the app locally:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
curl -s http://localhost:8000/voice/config-check
```

3. From the repository root on the host, run the automated grading commands. These commands execute through Docker Compose and do not require host Python packages or a local virtual environment:

```bash
make reproduce
make test
make lint
make loadtest
scripts/regenerate.sh
```

4. Open `docs/STORIES.md` and manually walk US-01 through US-10.
5. Compare screenshots in `docs/assets/stories/`.
6. Review `reports/phone_smoke_test.md` and `reports/walkthrough.md`.

## Troubleshooting

- If Docker reports that port `8000` is already in use, stop the existing process or change the Docker port mapping before rerunning `docker compose up --build`.
- Example diagnostic: `sudo lsof -i :8000`
- Example fix: stop the process using that port, then rerun `docker compose up --build`.
- Docker is required for the official grading/reproduction path.
- Local Python 3.13 is not supported by the pinned dependency stack used by this project. Docker handles Python 3.11 automatically through the Dockerfile.
- Developer-only note: if someone is debugging locally outside the grading flow, any direct Uvicorn/local-Python run is unsupported for grading and reproduction and should not be used as the TA/professor path.

## Submission Artifacts

- `docs/SPEC.md`
- `docs/STORIES.md`
- `docs/REPRODUCE.md`
- `docs/usage.md`
- `docs/MODEL_CARD.md`
- `docs/LOGGING.md`
- `grading/manifest.yaml`
- `grading/traceability.yaml`
- `reports/phone_smoke_test.md`
- `reports/walkthrough.md`
- `docs/assets/stories/us_01_expected.png` through `docs/assets/stories/us_10_expected.png`

## Reproducing Data and Indexes

Official one-command replay:

Run from the repository root on the host. This repository automation command executes through Docker Compose, does not replace `docker compose up --build`, and does not require host Python packages.

```bash
make reproduce
```

Helper commands for debugging the reproduction pipeline:

Run from the repository root on the host:

```bash
make download-data
make download-models
```

Expected generated files:
- `data/processed/menu.json`
- `data/index/menu_chunks.json`
- `data/index/menu_metadata.json`
- `data/index/embeddings.npy`

## Running Tests

Run from the repository root on the host. These commands execute through Docker Compose and are not an alternative app startup path.

```bash
make test
```

Expected reports:
- `reports/unit.xml`
- `reports/integration.xml`
- `reports/user_stories.xml`
- `reports/coverage.xml`
- `reports/coverage_html/`

Targets:
- business logic coverage target: at least 70 percent
- user-story pass target: at least 90 percent

## Linting and Security Checks

Run from the repository root on the host. These commands execute through Docker Compose and are not an alternative app startup path.

```bash
make lint
```

Tools:
- ruff
- black --check
- mypy
- pip-audit

Expected report:
- `reports/security.txt`

## Load Testing

Run from the repository root on the host. These commands execute through Docker Compose and are not an alternative app startup path.

```bash
make loadtest
```

Expected report:
- `reports/benchmarks.json`

Targets:
- 10 requests per second when resources allow
- under 5 percent error rate

## Demo Walkthrough

Run from the repository root on the host. These commands execute through Docker Compose and are not an alternative app startup path.

```bash
make demo
```
or:
```bash
scripts/demo.sh
```

The demo should exercise:
- greeting
- menu search
- dietary question
- add item
- modification
- total
- customer name
- readback
- confirmation

## Phone Path Verification

When Twilio credentials and public webhook are configured, the TA can verify phone behavior through:
1. spoken Twilio phone call
2. structured Docker logs
3. `twilio_call_sid`
4. `session_id`
5. `GET /api/debug/sessions/recent`
6. `GET /api/debug/session/{session_id}`

```bash
docker compose logs app | grep "<twilio_call_sid>"
curl http://localhost:8000/api/debug/sessions/recent
curl http://localhost:8000/api/debug/session/<session_id>
```

The phone call itself is the user interface; logs and debug routes provide grading observability.

## Project Documentation

- [docs/SPEC.md](docs/SPEC.md)
- [docs/STORIES.md](docs/STORIES.md)
- [docs/usage.md](docs/usage.md)
- [docs/DATA.md](docs/DATA.md)
- [docs/MODELS.md](docs/MODELS.md)
- [docs/REPRODUCE.md](docs/REPRODUCE.md)
- [docs/MODEL_CARD.md](docs/MODEL_CARD.md)
- [docs/LOGGING.md](docs/LOGGING.md)
- [docs/benchmarks.md](docs/benchmarks.md)
- [docs/diagrams/architecture.svg](docs/diagrams/architecture.svg)
- [grading/traceability.yaml](grading/traceability.yaml)
- [grading/manifest.yaml](grading/manifest.yaml)

## Generated Reports

| Report | Path | Generated By |
|---|---|---|
| Unit tests | `reports/unit.xml` | `make test` |
| Integration tests | `reports/integration.xml` | `make test` |
| User story tests | `reports/user_stories.xml` | `make test` |
| Coverage XML | `reports/coverage.xml` | `make test` |
| Coverage HTML | `reports/coverage_html/` | `make test` |
| Security audit | `reports/security.txt` | `make lint` |
| Benchmarks | `reports/benchmarks.json` | `make loadtest` |
| Walkthrough notes | `reports/walkthrough.md` | Manual walkthrough |
| Git contributions | `reports/git_contributions.txt` | contribution report command |

Run every `make ...` command in this table from the repository root on the host. These commands execute through Docker Compose and are not an alternative app startup path.

## Known Limitations

- no payment processing
- no payment card collection
- no real POS submission
- no guaranteed allergy safety
- no universal website scraping
- no real-time inventory unless represented in ingested menu
- Twilio live phone mode requires credentials and public webhook URL
- browser voice quality depends on browser and microphone
- menu answers are limited to ingested menu data

## Responsible AI and Safety Boundaries

- LLM cannot compute totals
- LLM cannot mutate order state directly
- LLM cannot invent menu items or prices
- MCP tools are authoritative for actions
- dietary/allergen claims must be grounded
- customer name and readback are required before confirmation
- payment collection is refused
- logs must not expose secrets or payment data

Read the full model card:
- [docs/MODEL_CARD.md](docs/MODEL_CARD.md)

## Project Structure

- `src/restaurant_agent/`
- `tests/`
- `docs/`
- `data/`
- `grading/`
- `scripts/`
- `reports/`

## Contribution Summary

- [CONTRIBUTIONS.md](CONTRIBUTIONS.md)
- `reports/git_contributions.txt`
