# Model and Service Documentation

## Overview

The system uses several model/service components:
- Anthropic Claude Haiku for language understanding and response phrasing.
- `sentence-transformers/all-MiniLM-L6-v2` for local semantic retrieval over menu chunks.
- Browser Web Speech API for local browser speech input and speech output.
- Twilio Programmable Voice for production phone-call speech input and output.
- Deterministic fallback parser for degraded LLM mode.

Deterministic MCP tools and application logic, not the LLM, are responsible for:
- order mutation
- pricing
- subtotal calculation
- tax calculation
- total calculation
- confirmation
- payment exclusion
- dietary/allergen safety boundaries

## Model and Service Inventory

| Component | Provider | Purpose | Required for Production Phone Mode | Required for Local Browser Walkthrough | Fallback |
|---|---|---|---:|---:|---|
| Anthropic Claude Haiku | Anthropic | Intent parsing, MCP tool-routing proposal, clarification wording, response phrasing | Yes | No | Deterministic degraded parser |
| `sentence-transformers/all-MiniLM-L6-v2` | Hugging Face / sentence-transformers | Local semantic embeddings for menu RAG | Yes | Yes | Structured filters + `rapidfuzz` lexical matching |
| Browser Web Speech API | Browser | Browser speech recognition and text-to-speech | No | Yes | Typed fallback for debugging/accessibility |
| Twilio Programmable Voice | Twilio | Real phone-call voice interface | Yes | No | Browser voice walkthrough |
| Deterministic fallback parser | Local application code | Safe degraded-mode intent parsing | No | No | Clarification or safe refusal |

## Anthropic Claude Haiku

```text
Provider: Anthropic
Default model: claude-haiku-4-5
Environment variable: ANTHROPIC_API_KEY
Optional model override: ANTHROPIC_MODEL
```

Purpose:
- caller intent classification
- item extraction
- quantity extraction
- modification extraction
- MCP tool-routing proposal
- clarification wording
- spoken response phrasing

Strict boundaries:
Claude Haiku shall not be used for:
- computing prices
- computing tax
- computing totals
- mutating order state directly
- confirming orders directly
- inventing menu items
- inventing prices
- inventing ingredients
- inventing allergens
- inventing dietary tags
- inventing modification prices
- processing payment
- making unsupported allergy-safe claims

Failure behavior:
If the Anthropic API key is missing, invalid, rate-limited, timed out, or the API returns an error, the system enters degraded LLM mode.

In degraded LLM mode:
- simple high-confidence requests may be handled by deterministic parsing
- complex or ambiguous order mutations are not performed
- dietary/allergen safety questions require caution or staff referral
- the system logs degraded mode with `request_id`

## Local Embedding Model

```text
Model: sentence-transformers/all-MiniLM-L6-v2
Package: sentence-transformers
Storage: data/index/embeddings.npy
Similarity: cosine similarity over normalized vectors
```

Purpose:
- generate embeddings for menu retrieval chunks
- support local semantic search over menu content
- improve natural-language menu question retrieval

It is prepared by:
```bash
make download-models
```
or during:
```bash
make reproduce
```

Failure behavior:
If the embedding model cannot be downloaded or loaded, the system enters degraded retrieval mode using:
- structured menu filters
- `rapidfuzz` fuzzy lexical matching

The app must not crash solely because vector embeddings are unavailable.

## Browser Web Speech API

Purpose:
- local browser microphone speech recognition
- browser text-to-speech for agent responses
- reproducible local walkthrough interface

Limitations:
- browser support varies
- microphone permission may be denied
- speech recognition quality depends on browser, microphone, OS, and environment
- automated backend tests do not require real microphone access

Fallback:
If browser speech is unavailable, the UI may provide typed fallback for debugging/accessibility. The project remains voice-first.

## Twilio Programmable Voice

Purpose:
- production phone-call interface
- incoming call webhook
- speech transcript webhook
- TwiML spoken responses
- call status callback

Required routes:
- `POST /voice/incoming`
- `POST /voice/turn`
- `POST /voice/status`
- `GET /voice/config-check`

Required environment variables when phone mode is enabled:
- `ENABLE_TWILIO=true`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`
- `TWILIO_WEBHOOK_BASE_URL`

Twilio is the primary production phone path. Automated tests simulate Twilio webhook payloads and do not require a real phone call.

If Twilio is disabled or credentials are missing:
- phone mode is disabled
- readiness should report phone mode disabled or misconfigured
- browser voice walkthrough remains available

## Deterministic Fallback Parser

```text
Module: src/restaurant_agent/fallback_parser.py
Type: Local deterministic application logic
```

Purpose:
- support safe degraded-mode behavior when Anthropic is unavailable
- parse simple high-confidence requests
- avoid total system failure when the LLM dependency fails

Supported intents:
- explicit menu search
- clearly named item add
- clearly named item remove
- simple item update
- simple modification such as “no onions”
- order summary
- compute total
- confirm after readback
- cancel order

Limitations:
The fallback parser shall not:
- perform broad recommendation reasoning
- handle complex ambiguous requests
- make allergy-safe claims
- invent menu items
- invent prices
- mutate ambiguous order state

If confidence is low, it must ask for rephrasing, clarification, or recommend speaking with restaurant staff.

## Degraded Mode Behavior

Two degraded modes are supported:

1. Degraded LLM mode:
   - Anthropic unavailable
   - deterministic parser handles only simple high-confidence requests
   - unsafe or ambiguous requests do not mutate order state

2. Degraded retrieval mode:
   - embedding model unavailable
   - system uses structured filters and `rapidfuzz` lexical matching
   - retrieval metadata records degraded status

Both degraded modes must be logged with `request_id`.

## Model and Service Limitations

- LLM output can be wrong, so MCP tools validate state changes.
- Speech recognition can mishear callers.
- RAG can retrieve the wrong item when queries are ambiguous.
- Menu data may be incomplete or outdated.
- Dietary/allergen data may be incomplete.
- Browser voice support varies by browser.
- Twilio requires valid credentials and public webhook configuration.
- No model or service guarantees allergy safety.
- No model or service processes payment.

## Model and Service Success Criteria

- `ANTHROPIC_MODEL` defaults to `claude-haiku-4-5`.
- `ANTHROPIC_API_KEY` is read only from environment variables.
- `sentence-transformers/all-MiniLM-L6-v2` is documented and used for embeddings.
- Embeddings are stored at `data/index/embeddings.npy`.
- Twilio routes are documented.
- Browser voice behavior is documented.
- Deterministic fallback parser behavior is documented.
- Degraded modes are documented.
- No undocumented model or service dependency is required.
