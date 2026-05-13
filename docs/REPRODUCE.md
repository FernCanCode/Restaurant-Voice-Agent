# Reproducibility Guide

## Overview

The project is fully reproducible from a clean repository clone using `.env.example`, `api_dependencies.yaml`, Docker Compose, and Makefile commands.

The official grading and reproduction path is Docker Compose. Docker is required. Graders should not create a local Python virtual environment manually, and should not treat local Python as a second supported run path. The Docker image uses Python 3.11 through the Dockerfile.

The default reproducibility path uses the committed raw menu fixture:

```text
data/raw/sample_restaurant_menu.html
```

and does not depend on live external restaurant websites.

The production phone path uses Twilio when credentials and a public webhook URL are configured.

## Hardware and Software Requirements

- Docker
- Docker Compose
- Make
- Git
- Chromium-based browser recommended for browser voice walkthrough
- Internet access for dependency/model download and external APIs
- Optional public webhook tunnel or public deployment URL for live Twilio phone testing

The local Docker app exposes port `8000`.

## Environment Variables

```bash
cp .env.example .env
```

After copying the environment template, the TA should fill values from `api_dependencies.yaml`.

Do not commit `.env` or any real credentials.

Important variables:

```text
ANTHROPIC_API_KEY
ANTHROPIC_MODEL
ENABLE_TWILIO
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_PHONE_NUMBER
TWILIO_WEBHOOK_BASE_URL
ENABLE_BROWSER_VOICE
MENU_RAW_FIXTURE_PATH
MENU_DATA_PATH
MENU_INDEX_PATH
HF_HOME
TRANSFORMERS_CACHE
ENABLE_DEBUG_ROUTES
```

- `ANTHROPIC_API_KEY` enables full LLM behavior.
- If Anthropic is missing or unavailable, degraded LLM mode should handle simple high-confidence requests safely.
- Twilio variables are required only when `ENABLE_TWILIO=true`.
- Browser voice walkthrough does not require Twilio credentials.
- `.env.example` contains placeholders only.
- Placeholder values are acceptable for local no-secret health/readiness checks.

## External API Dependencies

Please refer to:

```text
api_dependencies.yaml
```

Summarized dependencies:
- Anthropic Claude API
- Twilio Programmable Voice
- Browser Web Speech API
- Hugging Face / sentence-transformers model download

## Clean Clone Setup

```bash
git clone <repo_url>
cd <repo_name>
cp .env.example .env
# Edit .env and fill API keys listed in api_dependencies.yaml.
```

## Docker Compose Startup

Official grading/reproduction command:

```bash
docker compose up --build
```

Expected result:
- FastAPI app starts.
- App listens on `http://localhost:8000`.
- `GET /health` returns OK.
- Twilio routes are registered.
- Browser voice interface is available as the local walkthrough/fallback path.
- Twilio remains the primary production voice path when configured.
- The container runtime uses Python 3.11 from `python:3.11-slim`.

## Health and Readiness Checks

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
curl -s http://localhost:8000/voice/config-check
```

Expected health response:

```json
{
  "status": "ok",
  "service": "restaurant-voice-agent",
  "version": "0.1.0"
}
```

`/ready` reports menu, RAG, MCP, Anthropic, Twilio, browser voice, and degraded-mode status.

`/voice/config-check` reports whether Twilio is enabled/configured and lists any missing fields without exposing secrets.

## Public Twilio Webhook Verification

If live phone validation is required:

1. Expose the Docker app on port `8000` through a public HTTPS URL such as ngrok or cloudflared.
2. Set `TWILIO_WEBHOOK_BASE_URL` in `.env` to that public base URL.
3. Verify:

```bash
curl -s <PUBLIC_BASE_URL>/health
curl -s <PUBLIC_BASE_URL>/voice/config-check
```

Also verify local operator endpoints:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
curl -s http://localhost:8000/voice/config-check
```

4. In the Twilio Console, configure the phone number voice webhook as:

```text
POST <PUBLIC_BASE_URL>/voice/incoming
```

Optional status callback:

```text
POST <PUBLIC_BASE_URL>/voice/status
```

After a call, verify observability with:

```text
GET /api/debug/sessions/recent
GET /api/debug/session/{session_id}
```

## Troubleshooting

- If Docker reports that port `8000` is already in use, stop the existing process or adjust the port mapping, then rerun `docker compose up --build`.
- Example diagnostic: `sudo lsof -i :8000`
- Example fix: stop the process using that port, then rerun `docker compose up --build`.
- Local Python 3.13 is not supported by the pinned dependency stack used by this project. Docker handles Python 3.11 automatically through the Dockerfile.
- Developer-only note: direct local Uvicorn/Python runs are not the supported grading or reproduction path.

## Data Reproduction

```bash
make download-data
```

Expected behavior:
- verifies or prepares `data/raw/sample_restaurant_menu.html`
- creates required data directories
- does not fetch live restaurant websites during grading

## Model Preparation

```bash
make download-models
```

Expected behavior:
- prepares `sentence-transformers/all-MiniLM-L6-v2`
- uses local Hugging Face/sentence-transformers cache paths when configured
- does not download an external LLM
- does not require Anthropic API access

## Full Reproduction Command

```bash
make reproduce
```

Expected behavior:
- runs data preparation
- runs model preparation
- parses raw menu fixture
- writes canonical menu JSON
- builds RAG index
- runs tests or required validation checks
- generates reports

Expected generated data:

```text
data/processed/menu.json
data/index/menu_chunks.json
data/index/menu_metadata.json
data/index/embeddings.npy
```

If embeddings are unavailable, `menu_metadata.json` should document degraded retrieval mode.

## Test Reproduction

```bash
make test
```

Expected reports:

```text
reports/unit.xml
reports/integration.xml
reports/user_stories.xml
reports/coverage.xml
reports/coverage_html/
```

Expected thresholds:
- business-logic coverage at least 70 percent
- user-story automated test pass rate at least 90 percent

## Lint and Security Reproduction

```bash
make lint
```

Expected tools:
- `ruff`
- `black --check`
- `mypy`
- `pip-audit`

Expected output:

```text
reports/security.txt
```

Unresolved Critical or High vulnerabilities should fail the lint/security gate.

## Load Test Reproduction

```bash
make loadtest
```

Expected output:

```text
reports/benchmarks.json
```

Expected target:
- endpoint: `POST /api/turn`
- at least 10 requests per second when resources allow
- under 5 percent error rate
- 60-second window for full load test

## Demo Reproduction

```bash
make demo
```

or:

```bash
scripts/demo.sh
```

Expected behavior:
- exercises greeting
- menu search
- dietary question
- add item
- modification
- total
- customer name
- readback
- confirmation

The demo should not require Twilio.

## Expected Generated Artifacts

| Artifact | Path | Generated By |
|---|---|---|
| Processed menu | `data/processed/menu.json` | `make reproduce` |
| Menu chunks | `data/index/menu_chunks.json` | `make reproduce` |
| Menu metadata | `data/index/menu_metadata.json` | `make reproduce` |
| Embeddings | `data/index/embeddings.npy` | `make reproduce` / `make download-models` |
| Unit report | `reports/unit.xml` | `make test` |
| Integration report | `reports/integration.xml` | `make test` |
| User story report | `reports/user_stories.xml` | `make test` |
| Coverage XML | `reports/coverage.xml` | `make test` |
| Coverage HTML | `reports/coverage_html/` | `make test` |
| Security report | `reports/security.txt` | `make lint` |
| Benchmark report | `reports/benchmarks.json` | `make loadtest` |

## Expected Reports

- JUnit XML for test reporting
- coverage XML/HTML for coverage verification
- security report for dependency audit
- benchmarks report for load testing
- walkthrough report for manual validation

## Phone Path Reproduction

To test the phone path when credentials are available:

1. Set `ENABLE_TWILIO=true`.
2. Fill Twilio variables in `.env`.
3. Expose the app publicly through a deployment URL or approved webhook tunnel.
4. Configure the Twilio number voice webhook to:

```text
<public_base_url>/voice/incoming
```

5. Start the app.
6. Call the Twilio number.
7. Verify the spoken interaction.
8. Inspect structured logs.
9. Use:

```text
GET /api/debug/sessions/recent
GET /api/debug/session/{session_id}
```

to inspect phone session state.

Phone path grading can be verified through:
- spoken Twilio call interaction
- `twilio_call_sid`
- `session_id`
- structured logs
- debug session endpoints
- confirmed order state

## Browser Voice Walkthrough Reproduction

1. Start the app.
2. Open `http://localhost:8000`.
3. Click `Start Voice Order`.
4. Allow microphone permission.
5. Follow `docs/STORIES.md`.
6. Use typed fallback only if browser voice is unavailable.

Screenshots are stored under:

```text
docs/assets/stories/
```

## Troubleshooting

### Missing Anthropic API Key
Expected behavior:
- degraded LLM mode
- simple high-confidence requests still work
- complex ambiguous requests ask for rephrasing or staff support

### Twilio Disabled or Missing Credentials
Expected behavior:
- phone mode disabled or readiness reports misconfiguration
- browser voice walkthrough remains available

### Browser Microphone Denied
Expected behavior:
- UI displays message
- typed fallback available for debugging/accessibility

### Embedding Model Unavailable
Expected behavior:
- degraded retrieval mode
- structured filters and rapidfuzz lexical matching remain available
- app does not crash solely because embeddings are unavailable

### Missing Menu Fixture
Expected behavior:
- clear remediation message pointing to `data/raw/sample_restaurant_menu.html`

### Missing RAG Index
Expected behavior:
- run `make reproduce` or `POST /api/menu/rebuild-index`

### Payment Request
Expected behavior:
- agent refuses payment collection and explains payment is handled through normal restaurant process

## Reproduibility Success Criteria

- `docker compose up --build` starts the app.
- `GET /health` returns HTTP 200.
- `GET /ready` reports system readiness or documented degraded mode.
- `make download-data` succeeds.
- `make download-models` succeeds or fails with clear remediation.
- `make reproduce` generates menu JSON and RAG index artifacts.
- `make test` generates required reports.
- `make lint` generates `reports/security.txt`.
- `make loadtest` generates `reports/benchmarks.json`.
- Browser voice walkthrough can execute all user stories.
- Twilio phone path can be tested when credentials and public webhook URL are configured.
- No undocumented manual setup is required.
