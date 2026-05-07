# Regeneration Prompt

## Role

You are regenerating a specification-driven CS 6263 NLP and Agentic AI final project from the submitted specification documents. Your job is to implement the system described by the documents without inventing a different architecture.

## Project Summary

- Project name: Restaurant Voice Ordering Agent
- Package name: `restaurant_agent`
- Source root: `src/restaurant_agent/`
- It is a phone-capable restaurant voice ordering agent.
- Primary production path: Twilio Programmable Voice.
- Local reproducible walkthrough path: browser voice interface.
- Both paths use same backend agent, MCP tools, RAG index, order state, pricing logic, and structured logging.
- Payment processing is out of scope.

## Source of Truth Files

```text
docs/SPEC.md
docs/STORIES.md
grading/traceability.yaml
grading/manifest.yaml
api_dependencies.yaml
.env.example
docs/DATA.md
docs/MODELS.md
docs/REPRODUCE.md
docs/MODEL_CARD.md
docs/LOGGING.md
docs/usage.md
```

## Required Architecture

- FastAPI backend.
- Shared agent orchestrator.
- Twilio adapter.
- Browser voice adapter.
- MCP tool registry.
- Hybrid RAG menu retriever.
- Canonical menu JSON.
- Deterministic order store.
- Deterministic pricing.
- Session/dialogue state store.
- Structured JSON logging.
- Debug/session inspection routes for grading observability.

## Public Contracts That Must Not Change

These must not be renamed:
- package name
- source modules
- MCP tool names
- API routes
- story IDs
- data paths
- report paths
- environment variable names
- Makefile targets

## Required MCP Tools

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

## Required Public API Routes

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

## Required Data Paths

```text
data/raw/sample_restaurant_menu.html
data/processed/menu.json
data/index/menu_chunks.json
data/index/menu_metadata.json
data/index/embeddings.npy
```

## Required Report Paths

```text
reports/unit.xml
reports/integration.xml
reports/user_stories.xml
reports/coverage.xml
reports/coverage_html/
reports/benchmarks.json
reports/security.txt
reports/git_contributions.txt
reports/walkthrough.md
```

## Required User Stories

```text
US-01: Start a Browser Voice Call and Receive Greeting
US-02: Ask a Menu Question Using RAG
US-03: Ask a Dietary or Allergen Question
US-04: Add an Item with Quantity and Modification
US-05: Add an Unsupported Modification as a Special Instruction
US-06: Remove or Update an Item
US-07: Ask for Order Summary and Running Total
US-08: Provide Customer Name and Confirm Order
US-09: Error Path — Unknown Menu Item
US-10: Error Path — Ambiguous Removal or Item Reference
```

## Required Source Modules

```text
src/restaurant_agent/__init__.py
src/restaurant_agent/agent.py
src/restaurant_agent/api.py
src/restaurant_agent/config.py
src/restaurant_agent/demo_data.py
src/restaurant_agent/dietary.py
src/restaurant_agent/fallback_parser.py
src/restaurant_agent/llm_client.py
src/restaurant_agent/logging_config.py
src/restaurant_agent/mcp_server.py
src/restaurant_agent/menu_ingestion.py
src/restaurant_agent/menu_loader.py
src/restaurant_agent/menu_retriever.py
src/restaurant_agent/middleware.py
src/restaurant_agent/order_store.py
src/restaurant_agent/pricing.py
src/restaurant_agent/rag_index.py
src/restaurant_agent/schemas.py
src/restaurant_agent/security.py
src/restaurant_agent/session_store.py
src/restaurant_agent/twilio_voice.py
src/restaurant_agent/web.py
```

## Required Test Files

Scaffolded test files under:
- `tests/unit/`
- `tests/integration/`
- `tests/user_stories/`
- `tests/edge/`
- `tests/load/`

User story test files exactly:
```text
tests/user_stories/test_us_01_start_voice_call.py
tests/user_stories/test_us_02_menu_question_rag.py
tests/user_stories/test_us_03_dietary_question.py
tests/user_stories/test_us_04_add_item_with_modification.py
tests/user_stories/test_us_05_special_instruction.py
tests/user_stories/test_us_06_remove_or_update_item.py
tests/user_stories/test_us_07_summary_and_total.py
tests/user_stories/test_us_08_name_and_confirm.py
tests/user_stories/test_us_09_unknown_menu_item.py
tests/user_stories/test_us_10_ambiguous_removal.py
```

## Model and Service Requirements

- Anthropic Claude Haiku is the selected external LLM.
- Default model: `claude-haiku-4-5`.
- API key environment variable: `ANTHROPIC_API_KEY`.
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`.
- Twilio Programmable Voice is the production phone path.
- Browser Web Speech API is the local voice walkthrough path.
- Deterministic fallback parser handles degraded LLM mode.

## Safety and Scope Boundaries

- LLM must not compute totals.
- LLM must not mutate order state directly.
- LLM must not invent menu items.
- LLM must not invent prices.
- LLM must not invent ingredients.
- LLM must not make unsupported allergy-safe claims.
- Payment processing is out of scope.
- POS submission is out of scope.
- Universal website scraping is out of scope.
- Customer name is required before confirmation.
- Order readback is required before confirmation.
- Empty orders cannot be confirmed.
- Debug endpoints must not expose secrets, hidden prompts, or payment data.

## Reproducibility Requirements

```text
make install
make download-data
make download-models
make reproduce
make test
make lint
make loadtest
make demo
scripts/preflight.sh
scripts/demo.sh
scripts/regenerate.sh
```

- Docker Compose must start the app.
- `/health` and `/ready` must work.
- `.env.example` must be used.
- No secrets may be hardcoded.
- Default grading data path uses `data/raw/sample_restaurant_menu.html`.

## Output Requirements

- implement the specified source modules
- preserve public interfaces
- implement tests tied to user stories
- generate or preserve required reports through commands
- keep docs consistent
- do not remove required files

## Forbidden Changes

```text
Do not rename MCP tools.
Do not rename public API routes.
Do not rename source modules.
Do not rename user story IDs.
Do not rename data paths.
Do not rename report paths.
Do not replace Anthropic Claude Haiku with another unspecified model.
Do not replace sentence-transformers/all-MiniLM-L6-v2 with another unspecified embedding model.
Do not remove Twilio-compatible phone routes.
Do not remove browser voice fallback.
Do not add payment processing.
Do not add POS submission.
Do not make live website scraping required for grading.
Do not require real microphone access for automated tests.
Do not require a real Twilio call for automated tests.
Do not hardcode secrets.
Do not expose hidden prompts.
```

## Validation Expectations

- `make reproduce` should run.
- `make test` should run.
- `make lint` should run.
- `make loadtest` should run.
- user story tests should map to `docs/STORIES.md`.
- traceability should map stories to tests and modules.
- final implementation should satisfy `docs/SPEC.md`.
