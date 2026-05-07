# Restaurant Voice Ordering Agent Specification

## 1. Purpose
This document specifies the architecture, interfaces, and constraints for the Restaurant Voice Ordering Agent. The system shall function as a voice-first, Model Context Protocol (MCP)-enabled, Retrieval-Augmented Generation (RAG)-grounded restaurant ordering assistant. It provides a highly reliable, reproducible, and verifiable pathway for customers to query a menu, construct an order, and confirm it via spoken natural language.

Required log fields, event names, request ID propagation, Twilio call tracing, debug/session inspection, and sensitive-data exclusions are specified in docs/LOGGING.md.

Menu data provenance, fixture requirements, canonical menu schema details, and ingestion limitations are specified in docs/DATA.md.

Model and service dependencies are specified in docs/MODELS.md and api_dependencies.yaml.

Responsible AI limitations, risks, degraded-mode behavior, and out-of-scope capabilities are specified in docs/MODEL_CARD.md.

## 2. Target Users
- **Customers**: End-users placing food orders via telephone or browser voice interfaces.
- **Restaurant Operators**: Staff receiving finalized and confirmed orders with customer details.
- **Graders and Reviewers**: Evaluators utilizing the local browser interface for deterministic reproducibility and grading.

## 3. System Scope
The system shall encompass the complete voice-ordering lifecycle from initial greeting through menu exploration, item selection, modification, and final confirmation. The primary production interface shall be a Twilio-compatible phone voice endpoint, supported by a browser voice interface serving as a reproducible local grading path and backup interface. Both paths must utilize the exact same backend agent orchestrator, MCP tools, RAG index, order state, pricing logic, and structured logging mechanisms.

## 4. In-Scope Capabilities
- Spoken natural language input and output over telephony (Twilio) and browser interfaces.
- Menu ingestion from raw HTML fixtures, pasted text, uploaded files, or simple static URLs.
- Hybrid local RAG using structured filtering, rapidfuzz, and sentence-transformers for accurate menu retrieval.
- Dialogue state tracking and order state management.
- Intent classification, item extraction, quantity extraction, and modification extraction via Claude Haiku.
- Dietary and allergen querying based on explicit menu facts.
- Order calculation (pricing and totals) using deterministic Python logic.
- Final order confirmation requiring customer name and order readback.

## 5. Out-of-Scope Capabilities
- Payment processing, including the collection, processing, storage, transmission, or validation of payment card information.
- Direct Point-of-Sale (POS) integration and submission.
- Inventing or hallucinating menu items, prices, dietary tags, allergens, ingredients, or modifications.
- Unstructured order mutation directly by the LLM without traversing deterministic MCP tools.

## 6. Architecture Overview
The system relies on a hybrid architecture combining a non-deterministic LLM for intent parsing and dialogue generation with a deterministic Python backend for state and actions. The core components are:
1.  **Voice Interfaces**: Twilio (production) and Browser WebRTC/Audio (grading).
2.  **Agent Orchestrator**: Manages conversation turns, invoking the LLM, and dispatching tool executions.
3.  **LLM Layer**: Anthropic Claude Haiku (`claude-haiku-4-5`) handles intent classification, entity extraction, tool-routing proposals, and response phrasing.
4.  **MCP Tool Layer**: The authoritative action layer enforcing business rules.
5.  **State Managers**: Distinct systems for Order State and Dialogue State.
6.  **RAG Index**: Local NumPy-based vector and metadata storage for menu knowledge.

## 7. Component Inventory
The source code resides under `src/restaurant_agent/` and includes the following required modules:
- `__init__.py`
- `agent.py`
- `api.py`
- `config.py`
- `demo_data.py`
- `dietary.py`
- `fallback_parser.py`
- `llm_client.py`
- `logging_config.py`
- `mcp_server.py`
- `menu_ingestion.py`
- `menu_loader.py`
- `menu_retriever.py`
- `middleware.py`
- `order_store.py`
- `pricing.py`
- `rag_index.py`
- `schemas.py`
- `security.py`
- `session_store.py`
- `twilio_voice.py`
- `web.py`

## 8. Data Flow
1. **Input**: User speech is transcribed and submitted to the API.
2. **Orchestration**: The Agent orchestrator updates dialogue state and queries Claude Haiku with conversation history and available MCP tools.
3. **Reasoning**: Claude proposes an MCP tool call or generates a clarification response.
4. **Action**: The Agent executes the proposed MCP tool deterministically in Python.
5. **State Update**: Order state or context is updated. Results are appended to the dialogue.
6. **Output Generation**: Claude is re-prompted with tool results to generate a natural language spoken response.
7. **Delivery**: Text is synthesized to speech and delivered to the user.

## 9. Public Interfaces
The system shall expose the following public HTTP API routes:

| Route | Method | Description |
| :--- | :--- | :--- |
| `GET /` | GET | Root endpoint. |
| `GET /ui` | GET | Browser voice interface UI. |
| `GET /health` | GET | Health check. |
| `GET /ready` | GET | Readiness check. Reports readiness of menu loading, RAG index, MCP tool registry, order/session storage, Anthropic integration, Twilio integration, browser voice integration, and degraded-mode status. Returns HTTP 200 when the app can process at least degraded local requests. Returns HTTP 503 only when the system cannot process any agent turns. Does not expose secrets. |
| `GET /api/status` | GET | Detailed system status. |
| `POST /api/sessions` | POST | Create a new session. |
| `POST /api/turn` | POST | Accept a conversational turn from the browser. |
| `GET /api/sessions/{session_id}` | GET | Retrieve session state. |
| `GET /api/sessions/{session_id}/order` | GET | Retrieve current order state. |
| `POST /api/sessions/{session_id}/readback` | POST | Trigger an order readback. |
| `POST /api/sessions/{session_id}/confirm` | POST | Confirm an order. |
| `POST /api/sessions/{session_id}/cancel` | POST | Cancel a session/order. |
| `POST /voice/incoming` | POST | Twilio incoming call webhook. |
| `POST /voice/turn` | POST | Twilio conversation turn webhook. |
| `POST /voice/status` | POST | Twilio status callback webhook. |
| `GET /voice/config-check` | GET | Check Twilio configuration. |
| `POST /api/browser/start-call` | POST | Start browser voice call. |
| `POST /api/browser/voice-turn` | POST | Accept browser voice turn. |
| `POST /api/menu/ingest-text` | POST | Ingest menu from text. |
| `POST /api/menu/ingest-url` | POST | Ingest menu from URL. |
| `POST /api/menu/ingest-file` | POST | Ingest menu from file. |
| `POST /api/menu/rebuild-index` | POST | Rebuild RAG index. |
| `GET /api/menu/items` | GET | List menu items. |
| `GET /api/menu/items/{item_id}` | GET | Get specific menu item. |
| `POST /api/menu/search` | POST | Search menu via RAG. |
| `GET /api/logging/example` | GET | Generate example logs. |
| `GET /api/debug/sessions/recent` | GET | Return recent sessions for debugging. |
| `GET /api/debug/session/{session_id}` | GET | Return debug state for a session. |

### Minimal API Request and Response Schemas

#### POST /api/sessions

Request:

```json
{
  "channel": "browser",
  "caller_id": null
}
```

Response:

```json
{
  "session_id": "sess_example",
  "dialogue_mode": "GREETING",
  "agent_text": "Welcome to the restaurant voice ordering assistant...",
  "order": {
    "session_id": "sess_example",
    "customer_name": null,
    "status": "active",
    "items": [],
    "subtotal": 0.0,
    "tax": 0.0,
    "fees": 0.0,
    "total": 0.0,
    "currency": "USD",
    "confirmation_id": null
  },
  "next_action": "listen_for_user",
  "request_id": "req_example"
}
```

#### POST /api/turn

Request:

```json
{
  "session_id": "sess_example",
  "utterance": "Add two chicken tacos with no onions.",
  "channel": "browser",
  "speech_confidence": 0.95,
  "metadata": {
    "twilio_call_sid": null,
    "browser_user_agent": "example"
  }
}
```

Response:

```json
{
  "session_id": "sess_example",
  "dialogue_mode": "TAKING_ORDER",
  "intent": "add_order_item",
  "agent_text": "Added two chicken tacos with no onions. Your current total is $X.XX.",
  "speak": true,
  "order": {
    "session_id": "sess_example",
    "customer_name": null,
    "status": "active",
    "items": [],
    "subtotal": 0.0,
    "tax": 0.0,
    "fees": 0.0,
    "total": 0.0,
    "currency": "USD",
    "confirmation_id": null
  },
  "tool_calls": [
    {
      "tool_name": "add_order_item",
      "status": "success",
      "summary": "Added item to order."
    }
  ],
  "retrieval": {
    "used": true,
    "mode": "hybrid",
    "top_results": [],
    "confidence": 0.0
  },
  "requires_user_response": true,
  "next_action": "listen_for_user",
  "degraded_mode": false,
  "request_id": "req_example"
}
```

#### POST /voice/incoming

Request:
Twilio form-encoded webhook payload containing `CallSid` when provided by Twilio.

Response:
TwiML XML that speaks the greeting and gathers speech for `POST /voice/turn`.

#### POST /voice/turn

Request:
Twilio form-encoded webhook payload containing `CallSid` and speech transcript fields such as `SpeechResult`.

Response:
TwiML XML that speaks the agent response and either gathers another utterance or ends the call.

#### POST /api/menu/search

Request:

```json
{
  "query": "What tacos do you have?",
  "top_k": 5,
  "filters": {}
}
```

Response:

```json
{
  "query": "What tacos do you have?",
  "results": [],
  "retrieval_mode": "hybrid",
  "confidence": 0.0,
  "degraded_mode": false,
  "request_id": "req_example"
}
```

#### GET /api/debug/sessions/recent

Response:

```json
{
  "sessions": [
    {
      "session_id": "sess_example",
      "channel": "twilio",
      "twilio_call_sid": "CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "order_status": "active",
      "customer_name": "Fernando",
      "total": 12.34,
      "confirmation_id": null
    }
  ],
  "request_id": "req_example"
}
```

#### GET /api/debug/session/{session_id}

Response must include:
- session ID
- channel
- Twilio call SID when available
- dialogue mode
- customer name
- order status
- line items
- known modifications
- special instructions
- subtotal
- tax
- fees
- total
- confirmation ID
- recent tool-call summaries
- recent retrieval metadata
- degraded-mode flags
- request ID

## 10. Voice Interfaces
- **Twilio Voice**: The primary production interface. It shall handle TwiML generation, gathering user speech, and playing audio responses.
- **Browser Voice**: A fully capable local interface intended for testing, reproducible grading, and backup. It must support spoken input and spoken output. Typed input shall only exist as a fallback, accessibility, or debug mechanism. Both interfaces must route through the exact same agent orchestrator.

## 11. Menu Ingestion Strategy
The system shall support hybrid menu ingestion capable of parsing:
1. Committed raw HTML fixtures (e.g., `data/raw/sample_restaurant_menu.html`) primarily for deterministic grading.
2. Pasted text.
3. Uploaded files.
4. Simple static URL ingestion is supported only for publicly reachable HTML pages that return menu-like text in the initial HTTP response without requiring login, JavaScript rendering, CAPTCHA, third-party embedded menus, or PDF/image extraction. Live URL ingestion is not required for the default grading path.

## 12. Canonical Menu Schema
Ingested menus shall be converted into a structured representation encompassing categories, items, descriptions, prices, dietary tags, and allowable modifications. This canonical data shall be stored at:
```text
data/processed/menu.json
```

## 13. RAG Strategy
The system shall use a local hybrid RAG strategy for menu querying. Requirements include:
- **Python Structured Filtering**: Exact matching on categories or tags.
- **Fuzzy Matching**: Using `rapidfuzz` for robust text matching against menu item names.
- **Semantic Search**: Utilizing `sentence-transformers` and specifically the `sentence-transformers/all-MiniLM-L6-v2` model with cosine similarity.
- **Storage**: Local NumPy vector storage located under `data/index/`. The system shall utilize the following paths:
  ```text
  data/index/menu_chunks.json
  data/index/menu_metadata.json
  data/index/embeddings.npy
  ```

## 14. Dietary and Allergen Policy
- The LLM must not invent dietary tags, allergens, menu items, prices, ingredients, or modifications.
- Dietary and allergen claims must come from explicit menu evidence, restaurant-provided metadata, or conservative parser inference.
- Positive allergy-safe or dietary-safe claims require explicit menu evidence. If evidence is absent, the system must not guarantee safety.

## 15. MCP Tool Design
The system must use the following Model Context Protocol (MCP) tools exactly. These tools form the authoritative action layer. The agent orchestrator may interpret intent and select tools, but it must not directly mutate order state.

| Tool Name | Description |
| :--- | :--- |
| `search_menu` | Query the menu via RAG. |
| `get_menu_item` | Retrieve exact details of a specific item. |
| `check_dietary_info` | Verify allergens and dietary safety against menu facts. |
| `add_order_item` | Add an item to the current order state. |
| `remove_order_item` | Remove an item from the order state. |
| `update_order_item` | Modify an existing order item. |
| `get_order_summary` | Retrieve a human-readable list of current items. |
| `compute_total` | Calculate prices, taxes, and final totals. |
| `confirm_order` | Lock the order for finalization. |
| `cancel_order` | Abort the current session and clear the order. |

## 16. External LLM Provider and Responsibility Boundaries
- **Default External LLM**: Anthropic Claude Haiku (`claude-haiku-4-5`).
- **Configuration**: Authenticated via the `ANTHROPIC_API_KEY` environment variable.
- **Permitted LLM Responsibilities**:
  - Intent classification.
  - Item extraction.
  - Quantity extraction.
  - Modification extraction.
  - MCP tool-routing proposals.
  - Clarification wording.
  - Spoken response phrasing.
- **Prohibited LLM Responsibilities**:
  - Computing totals.
  - Mutating order state directly.
  - Inventing menu facts.
  - Inventing prices.
  - Confirming orders directly.
  - Payment processing.
  - Making unsupported allergy-safe claims.

## 17. Conversation Flow, Order State, and Dialogue State
Order state and dialogue state must be strictly separate. The order state manages deterministic variables (current items, total, customer name), while dialogue state manages the conversational transcripts and LLM history.

## Order State fields

Managed by:

```text
src/restaurant_agent/order_store.py
```

Fields:

```text
session_id: str
customer_name: str | None
status: Literal["active", "confirmed", "cancelled"]
items: list[OrderLineItem]
subtotal: float
tax: float
fees: float
total: float
currency: str
readback_performed: bool
confirmed_at: str | None
confirmation_id: str | None
```

## OrderLineItem fields

```text
line_item_id: str
item_id: str
item_name: str
quantity: int
base_unit_price: float
known_modifications: list[PricedModification]
special_instructions: list[str]
line_subtotal: float
line_total: float
```

## Dialogue State fields

Managed by:

```text
src/restaurant_agent/session_store.py
```

Fields:

```text
session_id: str
channel: Literal["browser", "twilio"]
twilio_call_sid: str | None
dialogue_mode: str
pending_action: str | None
pending_question: str | None
last_user_utterance: str | None
last_agent_response: str | None
last_intent: str | None
last_mentioned_item_id: str | None
last_retrieved_candidates: list
awaiting_final_confirmation: bool
order_readback_required: bool
turns: list[DialogueTurn]
degraded_llm: bool
degraded_retrieval: bool
request_ids: list[str]
```

## 18. Customer Name Collection and Confirmation Rules
The system enforces strict rules before an order can be confirmed:
1. The order state must include `customer_name`.
2. The system must collect the customer name before final confirmation.
3. The system must require a readback of the order to the customer before final confirmation.
4. The system must reject confirmation when:
   - The order is empty.
   - The customer name is missing.
   - The readback has not occurred.

## 19. Payment Processing Scope
Payment processing is entirely out of scope. The system shall not collect, process, store, transmit, or validate payment card information under any circumstances.

## 20. Error Handling and Degraded Modes
A degraded LLM mode must exist. In the event of primary LLM failure, the degraded mode must behave conservatively. In degraded LLM mode, the deterministic fallback parser handles only high-confidence requests from this supported intent list:

- explicit menu search by item name or category
- clearly named single item add with quantity
- clearly named single item remove
- simple item quantity update
- simple named modification such as “no onions”
- order summary request
- compute total request
- confirm order after readback
- cancel order

For any intent outside this list, or when confidence is low, the system shall ask for clarification, ask the caller to rephrase, or recommend speaking with restaurant staff. It shall not mutate order state on ambiguous input.

## 21. Reproducibility Requirements
All core flows must be fully reproducible locally without external telephony dependencies to support rigorous grading. The browser voice interface and the `data/raw/sample_restaurant_menu.html` fixture guarantee a consistent starting state.

## 22. Testing Requirements Summary
The project requires comprehensive testing separated into distinct suites:
- `tests/unit/`: Unit tests.
- `tests/integration/`: Integration tests.
- `tests/edge/`: Edge cases and prompt injection.
- `tests/user_stories/`: End-to-end user stories.
- `tests/load/`: Load testing with Locust.

The system shall output the following test and execution reports:
```text
reports/unit.xml
reports/integration.xml
reports/user_stories.xml
reports/coverage.xml
reports/coverage_html/
reports/benchmarks.json
reports/walkthrough.md
```

## 23. Code Quality and Responsible AI Requirements
- The source package name must be `restaurant_agent`, with all code located in `src/restaurant_agent/`.
- The system shall adhere to security guidelines to prevent prompt injection and data leakage.
- Security policies and vulnerabilities must be logged in `reports/security.txt`.
- Git history and developer contributions must be verifiable via `reports/git_contributions.txt`.

## 24. Logging and Operability Requirements

The system shall use structured JSON logging for all production code paths.

All tool executions, API requests, state mutations, LLM proposals, RAG retrievals, pricing calculations, confirmations, cancellations, and degraded-mode transitions shall be logged.

Required log fields, event names, request ID propagation, Twilio call tracing, debug/session inspection, and sensitive-data exclusions are specified in `docs/LOGGING.md`. The logging specification in `docs/LOGGING.md` is authoritative; this section summarizes the requirement.

Every HTTP response shall include an `X-Request-ID` header.

Logs shall never include API keys, Twilio auth tokens, hidden prompts, payment card data, `.env` contents, or raw secrets.

## 25. Phone Path Grading and Observability

The Twilio phone path shall be gradeable without relying only on audible phone output.

When a caller uses the Twilio phone interface, the system shall provide enough observability for a TA or instructor to verify the session, transcript, tool calls, order state, total, customer name, confirmation status, and confirmation ID.

Phone-mode observability shall include:

- structured JSON logs for every Twilio request
- `request_id` propagation through the Twilio adapter, agent orchestrator, MCP tools, RAG retrieval, pricing, and order store
- `twilio_call_sid` association with the internal `session_id`
- logged speech transcripts received from Twilio, excluding secrets or payment data
- logged MCP tool names and statuses
- logged RAG retrieval mode and confidence when retrieval is used
- logged order mutation events
- logged total calculation events
- logged confirmation or cancellation events
- a debug/session inspection endpoint for reviewing the current or final order state
- a way to look up a session by `session_id`
- a way to inspect or correlate Twilio sessions using `twilio_call_sid`

The existing debug endpoint:

`GET /api/debug/session/{session_id}`

shall return enough information for grading and debugging, including:

- session ID
- channel
- Twilio call SID when available
- dialogue mode
- customer name
- order status
- line items
- known modifications
- special instructions
- subtotal
- tax
- fees
- total
- confirmation ID
- recent tool-call summaries
- recent retrieval metadata
- degraded-mode flags

The system shall also expose or document a way to discover recent sessions during local grading.

The required route is:

`GET /api/debug/sessions/recent`

Purpose: Return recent sessions for local grading and debugging.

Required behavior:
- Returns recent session IDs.
- Includes channel for each session.
- Includes Twilio call SID when available.
- Includes order status.
- Includes customer name when available.
- Includes total.
- Includes confirmation ID when available.
- Does not expose secrets.
- May be disabled in production using `ENABLE_DEBUG_ROUTES=false`.

The phone path shall use the same backend agent, MCP tools, RAG index, order state, pricing logic, and structured logging as the browser voice path.

The browser UI may optionally display recent sessions or provide a session lookup field for grading convenience, but the backend debug routes and structured logs are the required observability mechanisms.

## 26. Data and Model Provenance Summary
Menu data originates from explicit ingestion sources. The system tracks provenance for `claude-haiku-4-5` (Anthropic) and `all-MiniLM-L6-v2` (SentenceTransformers). No external LLM is trained on customer order data.

## 27. Traceability Requirements
All requirements, user stories, and test executions must be traceable. System actions must map directly to the executed MCP tool to establish verifiable traceability during evaluation.

## 28. Final Scope Boundaries
The system is explicitly bounded to taking and confirming restaurant orders over voice. It serves as an orchestrator layer bridging LLM intent parsing and deterministic MCP tools. It does not fulfill orders, process payments, or connect directly to restaurant hardware.
