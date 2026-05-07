# Model Card

## Intended Use

The system is intended to help restaurant callers:
- ask menu questions
- ask basic ingredient, dietary, or allergen questions grounded in menu evidence
- add menu items to an order
- request item-level modifications
- save unsupported modifications as unpriced special instructions after caller confirmation
- remove or update order items
- hear running totals
- provide a customer name
- hear an order readback
- confirm or cancel an order

The system is intended for restaurant ordering workflows where menu content has been ingested into the canonical menu format and indexed for retrieval.

## System Components

The system relies on the following components:
- Anthropic Claude Haiku
- `sentence-transformers/all-MiniLM-L6-v2`
- MCP tools
- deterministic pricing logic
- deterministic order-state logic
- deterministic fallback parser
- Twilio Programmable Voice
- Browser Web Speech API
- structured logging and debug/session inspection routes

The LLM is only one component and is not the authority for prices, totals, order state, or dietary safety.

## Users and Use Context

Users include:
- restaurant callers
- restaurant staff or operators configuring menu content
- TA/instructor evaluating the project
- developers maintaining the project

Use contexts include:
- Twilio phone call ordering
- browser voice walkthrough
- automated user-story tests
- local grading through Docker Compose
- debugging through structured logs and debug endpoints

## LLM Role

```text
Provider: Anthropic
Default model: claude-haiku-4-5
Environment variable: ANTHROPIC_API_KEY
```

Allowed LLM responsibilities:
- caller intent classification
- item extraction
- quantity extraction
- modification extraction
- MCP tool-routing proposal
- clarification wording
- spoken response phrasing

Prohibited LLM responsibilities:
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
- exposing hidden prompts or secrets

## RAG Role

RAG is used only for menu-grounded knowledge tasks:
- menu search
- item lookup
- ingredient lookup
- dietary filtering
- allergen lookup
- modification availability
- item disambiguation

RAG is not used for:
- arithmetic
- tax calculation
- total calculation
- order mutation
- confirmation
- payment handling

Menu facts come solely from canonical menu JSON and generated RAG index artifacts.

## MCP Tool Role

MCP tools are the authoritative action layer. 

Required MCP tools:
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

Order mutation, dietary lookup, menu search, total calculation, confirmation, and cancellation must go through MCP tools.

## Limitations

- The system can only answer based on ingested menu content.
- The menu data may be incomplete or outdated.
- The system may not know real-time availability.
- The system may not know off-menu substitutions.
- Speech recognition may mishear callers.
- RAG retrieval may return imperfect matches.
- The LLM may misunderstand caller intent.
- The browser voice interface depends on browser support and microphone permission.
- Twilio phone mode requires valid credentials and a public webhook URL.
- The system cannot guarantee allergy safety unless explicit menu evidence supports the claim.
- The system does not process payment.
- The system does not submit orders to a real POS.

## Risks

- incorrect order due to speech recognition error
- incorrect order due to LLM misclassification
- wrong menu item due to ambiguous item name
- wrong modification due to ambiguous instruction
- unsupported modification mistaken as priced
- total inconsistency if arithmetic is not deterministic
- dietary/allergen overclaiming
- caller believes payment has been processed when it has not
- external API outage or rate limit
- incomplete menu data
- debug logs accidentally exposing sensitive data if logging safeguards are not followed

## Risk Mitigations

- deterministic MCP tools for order mutation
- deterministic pricing and total calculation
- required readback before final confirmation
- required customer name before final confirmation
- rejection of empty order confirmation
- rejection of confirmation without readback
- clarification when item, quantity, modification, or removal target is ambiguous
- cautious dietary/allergen language
- degraded LLM mode with conservative behavior
- degraded retrieval mode with structured and lexical matching
- structured logging with secret redaction
- payment exclusion policy
- automated unit, integration, user-story, edge, and load tests
- debug/session inspection routes for phone-path grading

## Out of Scope

The following are completely out of scope:
- payment processing
- credit card collection
- debit card collection
- CVV collection
- billing address collection
- PCI compliance
- real POS submission
- kitchen ticket printing
- delivery address collection
- refunds
- loyalty accounts
- coupons
- guaranteed allergy safety
- medical advice
- nutritional advice
- universal website scraping
- full production call-center routing
- live human transfer unless separately configured

## Safety Boundaries

- The system shall not collect payment card information.
- The system shall not process payments.
- The system shall not claim an order is paid.
- The system shall not guarantee allergy safety without explicit menu evidence.
- The system shall not invent unavailable menu items.
- The system shall not invent prices.
- The system shall not allow the LLM to compute totals.
- The system shall not allow the LLM to mutate order state directly.
- The system shall not confirm an empty order.
- The system shall not confirm without a customer name.
- The system shall not confirm without order readback.
- The system shall not expose hidden prompts, API keys, or secrets.

## Privacy and Data Handling

Allowed collected data:
- caller utterances/transcripts
- menu questions
- order items
- modifications
- special instructions
- customer name
- session ID
- Twilio call SID when phone mode is enabled
- request IDs
- confirmation ID
- order status and totals

Data that should not be collected:
- payment card data
- CVV
- billing address
- government ID numbers
- Social Security numbers
- passwords
- API keys from callers
- sensitive medical details beyond caller-provided dietary/allergen questions

Logs must not include secrets, payment card numbers, or hidden prompts.

## Degraded Mode Behavior

### Degraded LLM Mode

Triggered by:
- missing Anthropic API key
- invalid key
- timeout
- rate limit
- API outage
- invalid LLM response

Behavior:
- deterministic fallback parser handles simple high-confidence requests
- complex or ambiguous order mutations are not performed
- dietary/allergen safety questions remain cautious
- system asks for clarification, rephrasing, or staff support when necessary
- event is logged with `request_id`

### Degraded Retrieval Mode

Triggered by:
- embedding model unavailable
- embedding model download failure
- vector index unavailable

Behavior:
- structured filters remain available
- `rapidfuzz` lexical matching remains available
- vector retrieval is disabled
- menu metadata records degraded retrieval status
- event is logged with `request_id`

## Evaluation and Testing

Safety and quality are evaluated through:
- unit tests
- integration tests
- user-story acceptance tests
- edge-case tests
- prompt-injection tests
- dependency-failure tests
- confirmation-rule tests
- dietary/allergen safety tests
- load tests
- manual walkthroughs
- structured log tracing

Required reports:
```text
reports/unit.xml
reports/integration.xml
reports/user_stories.xml
reports/coverage.xml
reports/benchmarks.json
reports/security.txt
```

## Model Card Success Criteria

- Intended Use section exists.
- Limitations section exists.
- Risks section exists.
- Out of Scope section exists.
- LLM responsibilities and prohibitions are documented.
- MCP tool authority is documented.
- RAG boundaries are documented.
- Payment exclusion is documented.
- Dietary/allergen uncertainty is documented.
- Degraded modes are documented.
- Privacy/logging boundaries are documented.
- Safety-related tests are documented.
