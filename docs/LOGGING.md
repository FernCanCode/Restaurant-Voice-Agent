# Logging and Observability Guide

## Overview

The system uses structured JSON logs to support debugging, grading, and operation. Every request must have a `request_id`. Twilio phone sessions must also include `twilio_call_sid` when available.

Logs must allow a TA to trace:
- incoming request
- speech transcript receipt
- agent turn start
- LLM/degraded parser behavior
- MCP tool calls
- RAG retrieval
- order mutation
- pricing/total calculation
- response generation
- confirmation or cancellation

## Logging Goals

- support grading and manual walkthrough verification
- support Twilio phone-path verification
- support debugging without exposing secrets
- connect logs across routes, agent, tools, retrieval, pricing, and order state
- make degraded modes visible
- show request latency and tool status where useful

## Required Log Format

Production code paths must use structured JSON logging. Bare `print()` statements should not be used in production code paths.

Example:
```json
{
  "timestamp": "2026-05-04T20:15:30.123Z",
  "level": "INFO",
  "module": "restaurant_agent.agent",
  "event": "agent_turn_completed",
  "message": "Agent turn completed successfully.",
  "request_id": "req_123",
  "session_id": "sess_456",
  "channel": "twilio"
}
```

## Required Log Fields

Minimum fields:
- `timestamp`
- `level`
- `module`
- `event`
- `message`
- `request_id`

Contextual fields when available:
- `session_id`
- `channel`
- `dialogue_mode`
- `intent`
- `tool_name`
- `tool_status`
- `tool_latency_ms`
- `retrieval_mode`
- `top_score`
- `result_count`
- `degraded_mode`
- `provider`
- `model`
- `llm_latency_ms`
- `llm_status`
- `twilio_call_sid`
- `confirmation_id`

## Request ID Propagation

- If an incoming request has `X-Request-ID`, use it.
- If not, generate a UUID.
- Add `X-Request-ID` to the response headers.
- Propagate the same request ID through:
  - FastAPI route handler
  - Twilio adapter
  - browser adapter
  - agent orchestrator
  - LLM client
  - fallback parser
  - MCP tool registry
  - menu retriever
  - dietary policy
  - order store
  - pricing
  - response generation

Trace command:
```bash
docker compose logs app | grep "<request_id>"
```

## Twilio Call Tracing

Twilio phone sessions must log:
- `twilio_incoming_call`
- `twilio_speech_received`
- `twilio_response_generated`
- `twilio_call_status`

Each Twilio log should include when available:
- `request_id`
- `session_id`
- `twilio_call_sid`
- `channel=twilio`
- speech transcript received from Twilio
- call status
- response status

The system must map Twilio `CallSid` to internal `session_id`.

A TA can verify a phone call using:
1. the spoken Twilio call
2. `twilio_call_sid`
3. `session_id`
4. Docker Compose logs
5. `GET /api/debug/sessions/recent`
6. `GET /api/debug/session/{session_id}`

## Browser Voice Tracing

Browser voice sessions must log:
- `browser_call_started`
- `browser_transcript_received`
- `browser_response_returned`

Each browser log should include:
- `request_id`
- `session_id`
- `channel=browser`
- transcript
- agent response summary

Browser voice and Twilio phone paths must converge into the same agent orchestrator.

## Agent Turn Tracing

Documented events:
- `agent_turn_started`
- `intent_classified`
- `tool_routing_selected`
- `agent_response_generated`
- `agent_turn_completed`
- `agent_turn_failed`

Each agent turn log should include:
- `request_id`
- `session_id`
- `channel`
- `dialogue_mode`
- `intent`
- `degraded_mode`

## MCP Tool Logging

Documented events:
- `mcp_tool_started`
- `mcp_tool_completed`
- `mcp_tool_failed`

Each MCP tool log should include:
- `request_id`
- `session_id`
- `tool_name`
- `tool_status`
- `tool_latency_ms`
- short summary

Required MCP tools:
- `search_menu`
- `get_menu_item`
- `check_dietary_info`
- `add_order_item`
- `remove_order_item`
- `update_order_item`
- `get_order_summary`
- `compute_total`
- `confirm_order`
- `cancel_order`

## RAG Retrieval Logging

Documented events:
- `rag_retrieval_started`
- `rag_retrieval_completed`
- `rag_retrieval_failed`
- `rag_degraded_mode_enabled`

Each RAG log should include:
- `request_id`
- `session_id`
- `query`
- `retrieval_mode`
- `top_score`
- `result_count`
- `confidence`
- `degraded_mode`

RAG logs should not invent or hide retrieval failures.

## Order State Logging

Documented events:
- `order_item_added`
- `order_item_removed`
- `order_item_updated`
- `order_summary_requested`
- `order_total_computed`
- `order_readback_generated`
- `customer_name_recorded`
- `order_confirmation_requested`
- `order_confirmed`
- `order_cancelled`
- `order_confirmation_rejected`

Order logs should include:
- `request_id`
- `session_id`
- `order_status`
- `line_item_count`
- `subtotal`
- `tax`
- `fees`
- `total`
- `confirmation_id` when available

Order logs must not include payment information.

## Degraded Mode Logging

Degraded LLM mode events:
- `llm_request_failed`
- `llm_degraded_mode_enabled`

Degraded retrieval mode events:
- `embedding_model_unavailable`
- `rag_degraded_mode_enabled`

Each degraded-mode log should include:
- `request_id`
- `session_id` when available
- error type
- provider or dependency name
- fallback behavior
- whether order mutation was allowed or refused

## Debug and Session Inspection Routes

```text
GET /api/debug/sessions/recent
GET /api/debug/session/{session_id}
```

For `GET /api/debug/sessions/recent`, it returns:
- recent session IDs
- channel
- Twilio call SID when available
- order status
- customer name when available
- total
- confirmation ID when available

For `GET /api/debug/session/{session_id}`, it returns:
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

- Debug routes must not expose secrets.
- Debug routes must not expose hidden prompts.
- Debug routes must not expose payment card data.
- Debug routes may be disabled in production with `ENABLE_DEBUG_ROUTES=false`.

## Example End-to-End Trace

Utterance:
```text
Add two chicken tacos with no onions.
```

```json
{"timestamp": "2026-05-04T20:15:30.123Z", "level": "INFO", "module": "restaurant_agent.api", "event": "browser_call_started", "message": "Received turn transcript: Add two chicken tacos with no onions.", "request_id": "req_example_001", "session_id": "sess_example_001", "channel": "browser"}
{"timestamp": "2026-05-04T20:15:30.150Z", "level": "INFO", "module": "restaurant_agent.agent", "event": "agent_turn_started", "message": "Starting agent turn", "request_id": "req_example_001", "session_id": "sess_example_001"}
{"timestamp": "2026-05-04T20:15:30.500Z", "level": "INFO", "module": "restaurant_agent.agent", "event": "intent_classified", "message": "Intent: add_item", "request_id": "req_example_001", "session_id": "sess_example_001", "intent": "add_item"}
{"timestamp": "2026-05-04T20:15:30.510Z", "level": "INFO", "module": "restaurant_agent.mcp_server", "event": "mcp_tool_started", "message": "Executing add_order_item", "request_id": "req_example_001", "session_id": "sess_example_001", "tool_name": "add_order_item"}
{"timestamp": "2026-05-04T20:15:30.520Z", "level": "INFO", "module": "restaurant_agent.order_store", "event": "order_item_added", "message": "Added 2 Chicken Tacos", "request_id": "req_example_001", "session_id": "sess_example_001", "line_item_count": 1}
{"timestamp": "2026-05-04T20:15:30.530Z", "level": "INFO", "module": "restaurant_agent.pricing", "event": "order_total_computed", "message": "Computed totals", "request_id": "req_example_001", "session_id": "sess_example_001", "subtotal": 10.00, "total": 10.83}
{"timestamp": "2026-05-04T20:15:31.200Z", "level": "INFO", "module": "restaurant_agent.agent", "event": "agent_response_generated", "message": "Added two chicken tacos with no onions. Your current total is $10.83.", "request_id": "req_example_001", "session_id": "sess_example_001"}
{"timestamp": "2026-05-04T20:15:31.210Z", "level": "INFO", "module": "restaurant_agent.agent", "event": "agent_turn_completed", "message": "Turn completed", "request_id": "req_example_001", "session_id": "sess_example_001"}
```

## Sensitive Data Exclusions

Logs must not include:
- Anthropic API key
- Twilio auth token
- `.env` contents
- hidden prompts
- payment card numbers
- CVV codes
- full raw secrets
- passwords
- government ID numbers
- unnecessary sensitive personal information

If a caller tries to provide payment information, the system should avoid storing it and should redirect the caller to the payment exclusion message.

## Troubleshooting With Logs

Commands:
```bash
docker compose logs app | grep "<request_id>"
docker compose logs app | grep "<twilio_call_sid>"
curl http://localhost:8000/api/debug/sessions/recent
curl http://localhost:8000/api/debug/session/<session_id>
```

- finding a request by `request_id`: grep logs for the ID
- finding a Twilio call by `twilio_call_sid`: grep logs or use debug endpoints
- finding recent sessions: `curl http://localhost:8000/api/debug/sessions/recent`
- checking whether Anthropic is degraded: look for `llm_degraded_mode_enabled`
- checking whether RAG is degraded: look for `rag_degraded_mode_enabled`
- checking why an item was not added: check `mcp_tool_failed` or `intent_classified`
- checking why confirmation was rejected: check `order_confirmation_rejected`
- checking order total calculation: check `order_total_computed`

## Logging Success Criteria

- every HTTP response includes `X-Request-ID`
- every log entry includes `request_id`
- Twilio logs include `twilio_call_sid` when available
- browser logs include `channel=browser`
- MCP tool calls are logged
- RAG retrievals are logged
- order mutations are logged
- total calculations are logged
- degraded modes are logged
- confirmation and cancellation are logged
- logs avoid secrets and payment data
- a TA can trace one browser session end-to-end
- a TA can trace one Twilio phone session end-to-end
