# CLAUDE.md

## Project Overview

- Project name: Restaurant Voice Ordering Agent.
- Package name: `restaurant_agent`.
- Source root: `src/restaurant_agent/`.
- This is a phone-capable restaurant voice ordering agent.
- Production phone path uses Twilio Programmable Voice.
- Local reproducible walkthrough path uses browser voice.
- Both paths must use the same backend agent, MCP tools, RAG index, order state, pricing logic, and structured logging.

## Source of Truth

```text
docs/SPEC.md
docs/STORIES.md
grading/traceability.yaml
grading/manifest.yaml
api_dependencies.yaml
.env.example
docs/REPRODUCE.md
docs/MODEL_CARD.md
docs/LOGGING.md
```

If implementation conflicts with the spec, either fix the implementation or explicitly ask before changing the spec.

## Non-Negotiable Public Contracts

MCP Tools:
```text
search_menu
get_menu_item
check_dietary_info
add_order_item
remove_order_item
update_order_item
get_order_summary
compute_total
confirm_order
cancel_order
```

API Routes:
```text
GET /
GET /ui
GET /health
GET /ready
GET /api/status
POST /api/sessions
POST /api/turn
GET /api/sessions/{session_id}
GET /api/sessions/{session_id}/order
POST /api/sessions/{session_id}/readback
POST /api/sessions/{session_id}/confirm
POST /api/sessions/{session_id}/cancel
POST /voice/incoming
POST /voice/turn
POST /voice/status
GET /voice/config-check
POST /api/browser/start-call
POST /api/browser/voice-turn
POST /api/menu/ingest-text
POST /api/menu/ingest-url
POST /api/menu/ingest-file
POST /api/menu/rebuild-index
GET /api/menu/items
GET /api/menu/items/{item_id}
POST /api/menu/search
GET /api/logging/example
GET /api/debug/sessions/recent
GET /api/debug/session/{session_id}
```

Do not rename public routes, MCP tools, source modules, story IDs, data paths, report paths, Makefile targets, or environment variable names without explicit human approval.

## Architecture Rules

- FastAPI route handlers should be thin.
- Business logic belongs in service modules.
- Both Twilio and browser voice paths must call the shared agent orchestrator.
- MCP tools are the authoritative action layer.
- The LLM may propose tool routing but must not mutate order state.
- RAG handles menu-grounded retrieval only.
- Pricing and totals must be deterministic.
- Order state and dialogue state must remain separate.
- Debug/session routes must support phone-path grading observability.
- Structured logs must include request IDs.

## Safety and Scope Rules

- Do not implement payment processing.
- Do not collect credit card numbers, CVV, billing address, or payment credentials.
- Do not implement real POS submission.
- Do not claim universal website scraping.
- Do not guarantee allergy safety without explicit menu evidence.
- Do not allow the LLM to compute totals.
- Do not allow the LLM to invent menu items or prices.
- Do not expose hidden prompts, API keys, or secrets.
- Require customer name before confirmation.
- Require order readback before confirmation.
- Reject empty order confirmation.

## Development Workflow

- Work one phase at a time.
- Do not implement the entire project in one broad pass.
- Modify only files relevant to the current phase unless a supporting change is necessary.
- After each phase, run the phase-specific validation commands.
- Report files changed, commands run, command outputs, failures, and acceptance status.
- If validation fails, fix the current phase before moving on.
- Do not delete tests to make checks pass.
- Do not silently change public contracts.

## Validation Commands

```bash
make install
make download-data
make download-models
make reproduce
make test
make lint
make loadtest
make demo
scripts/preflight.sh
```

Targeted commands:
```bash
pytest tests/unit -q
pytest tests/integration -q
pytest tests/user_stories -q
pytest tests/edge -q
ruff check src tests
black --check src tests
mypy src
```

## Testing Expectations

- Unit tests should not require live Anthropic, Twilio, browser microphone, or live restaurant websites.
- Integration tests may simulate Twilio webhook payloads.
- User-story tests must map to `docs/STORIES.md`.
- Edge tests must cover prompt injection, payment requests, unsupported allergy claims, ambiguous orders, missing names, missing readback, invalid quantities, missing dependencies, and degraded modes.
- Load tests should target `POST /api/turn`.
- Coverage target is at least 70 percent over business logic.
- User-story pass target is at least 90 percent.

## Documentation Expectations

- Keep `docs/SPEC.md`, `docs/STORIES.md`, `docs/usage.md`, and `grading/traceability.yaml` consistent.
- Do not leave TODOs in final submitted docs except where explicitly appropriate for placeholder reports before execution.
- Do not include informal planning notes.
- Keep screenshot paths aligned with `docs/STORIES.md`.
- Final screenshots are captured later after UI works.

## Before Changing Public Contracts

If a change seems necessary to:
- route names
- MCP tool names
- model choices
- data paths
- report paths
- source module names
- user story IDs
- environment variable names

then stop and ask for approval before changing it.

## Final Submission Reminders

- No real `.env` file.
- No committed API keys.
- No payment processing.
- No hidden prompt exposure.
- No unsupported allergy-safe claims.
- Docker Compose must start the app.
- `/health` and `/ready` must work.
- `make test`, `make lint`, and `make loadtest` must generate required reports.
- Twilio phone path must be observable through logs and debug/session endpoints.
- Browser voice path must support reproducible manual walkthrough.
