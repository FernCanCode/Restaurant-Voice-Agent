# Restaurant Voice Ordering Agent Usage Guide

## Overview

The Restaurant Voice Ordering Agent is a voice-first system capable of assisting users with menu inquiries and taking food orders. The agent can:
- Answer menu questions
- Answer grounded dietary and allergen questions cautiously
- Add items to an order
- Handle modifications
- Handle unpriced special instructions after confirmation
- Remove or update items
- Compute running totals
- Collect customer name
- Read back the order
- Confirm or cancel the order

All order actions go through deterministic Model Context Protocol (MCP) tools, and all menu answers are grounded directly in the ingested menu and Retrieval-Augmented Generation (RAG) index.

## Local Browser Voice Walkthrough

The browser interface serves as the reproducible local walkthrough interface. A Chromium-based browser is recommended.

1. Start the app with Docker Compose.
2. Open `http://localhost:8000`.
3. Click `Start Voice Order`.
4. Allow microphone permission if prompted.
5. Speak the sample utterances from the user-story sections.
6. Watch the transcript, order panel, total panel, and status indicators.
7. Use typed fallback only if browser voice input is unavailable.

## Production Phone Mode

Production phone mode uses Twilio Programmable Voice routes:
- `POST /voice/incoming`
- `POST /voice/turn`
- `POST /voice/status`
- `GET /voice/config-check`

Twilio setup requires configuring environment variables documented in `.env.example` and `api_dependencies.yaml`. Twilio is **not required** for the local browser walkthrough.

### Verifying a Twilio Phone Session

When testing the phone path, the TA can verify the call through:

1. The spoken Twilio call interaction.
2. Docker Compose logs filtered by `request_id` or `twilio_call_sid`.
3. `GET /api/debug/sessions/recent` to find recent sessions.
4. `GET /api/debug/session/{session_id}` to inspect order state, customer name, total, confirmation status, and recent tool-call summaries.

The phone path does not require a separate visual phone UI. The phone call is the user interface; logs and debug/session endpoints provide grading observability.

## General Troubleshooting

- **Microphone Permission Denied**: Check browser settings and ensure the site is allowed to use the microphone.
- **Browser Speech Recognition Unavailable**: Use the typed utterance fallback for debugging and accessibility.
- **Anthropic API Key Missing**: The app will enter degraded LLM mode rather than crashing. Ensure `ANTHROPIC_API_KEY` is set in `.env`.
- **Twilio Disabled**: Set `ENABLE_TWILIO=true` in `.env` and verify webhook paths to enable production phone mode.
- **Menu Index Missing**: Ensure the data download and index generation scripts have run.
- **Embedding Model Unavailable**: The system will fall back to degraded retrieval mode (using lexical matching instead of semantic embeddings) rather than crashing.
- **Unsupported Item**: The agent will reject adding items not found in the indexed menu.
- **Ambiguous Request**: The agent will ask for clarification before modifying the order state.
- **Payment Request**: The system intentionally does not handle payments; it will advise that payment happens upon pickup or via another system.

## US-01: Start a Browser Voice Call and Receive Greeting

### Goal
Start a voice order session.

### Steps
1. Open `http://localhost:8000`.
2. Click `Start Voice Order`.
3. Allow microphone permission if prompted.
4. Listen for the greeting.
5. Verify the transcript and empty order panel.

### Expected Result
The agent greets the caller aloud and displays an empty active order with total `$0.00`.

### Troubleshooting
If no audio plays, check browser audio permissions and use the transcript panel to verify the response.

## US-02: Ask a Menu Question Using RAG

### Goal
Ask a menu question that requires RAG.

### Steps
1. Start a voice session.
2. Say: “What tacos do you have?”
3. Verify taco items are listed from the menu.
4. Verify no off-menu items are invented.

### Expected Result
The agent returns taco items from the indexed menu with names and prices when available.

### Troubleshooting
If the agent cannot find tacos, verify the menu fixture and RAG index were generated.

## US-03: Ask a Dietary or Allergen Question

### Goal
Ask a dietary/allergen question.

### Steps
1. Start a voice session.
2. Say: “Do you have anything vegetarian?”
3. Say: “Is the black bean bowl safe for a peanut allergy?”
4. Verify cautious, grounded wording.

### Expected Result
The agent answers from menu evidence and does not guarantee allergy safety without explicit evidence.

### Troubleshooting
If the agent gives an unsupported safety guarantee, this violates the dietary/allergen policy and should be fixed.

## US-04: Add an Item with Quantity and Modification

### Goal
Add an item with quantity and modification.

### Steps
1. Start a voice session.
2. Say: “Add two chicken tacos with no onions.”
3. Verify quantity, item, modification, and total.

### Expected Result
The order shows two Chicken Tacos with the `no onions` modification and updated total.

### Troubleshooting
If no onions is ignored, check modification parsing and order-state storage.

## US-05: Add an Unsupported Modification as a Special Instruction

### Goal
Add an unsupported modification as a special instruction.

### Steps
1. Start a voice session.
2. Say: “Add one chicken taco with extra queso.”
3. Confirm when the agent asks whether to save it as a special instruction.
4. Verify it appears as a special instruction and does not change price.

### Expected Result
The system does not invent a price for extra queso. It stores the request as an unpriced special instruction after caller confirmation.

### Troubleshooting
If the system charges for extra queso without a menu price, pricing logic is incorrect.

## US-06: Remove or Update an Item

### Goal
Remove or update an item.

### Steps
1. Start a voice session.
2. Say: “Add two chicken tacos.”
3. Say: “Change that to one chicken taco.”
4. Say: “Remove the chicken taco.”
5. Verify total updates after each change.

### Expected Result
Quantity changes from two to one, then the item is removed and total returns to `$0.00`.

### Troubleshooting
If removal targets the wrong item, check dialogue state and removal clarification logic.

## US-07: Ask for Order Summary and Running Total

### Goal
Ask for current order summary and running total.

### Steps
1. Start a voice session.
2. Say: “Add one chicken taco with no onions.”
3. Say: “Add one lemonade.”
4. Say: “What is my total?”
5. Say: “Read back my order.”

### Expected Result
The agent reads item names, quantities, modifications, subtotal, tax, fees, and total.

### Troubleshooting
If totals are inconsistent, check `compute_total` and pricing data.

## US-08: Provide Customer Name and Confirm Order

### Goal
Provide customer name and confirm order.

### Steps
1. Start a voice session.
2. Say: “Add one chicken taco with no onions.”
3. Say: “Put the order under Fernando.”
4. Say: “That is everything.”
5. Listen to the readback.
6. Say: “Yes, confirm.”
7. Verify confirmation ID.

### Expected Result
The order is confirmed under Fernando and a confirmation ID is displayed.

### Troubleshooting
If the system confirms without name or readback, confirmation rules are incorrect.

## US-09: Error Path — Unknown Menu Item

### Goal
Verify unknown menu items are rejected safely.

### Steps
1. Start a voice session.
2. Say: “Add one lobster pizza.”
3. Verify no item is added.
4. Verify total remains `$0.00`.

### Expected Result
The agent says it cannot find lobster pizza on the menu and asks the caller to choose an available item.

### Troubleshooting
If lobster pizza is added, the system is inventing menu items and must be fixed.

## US-10: Error Path — Ambiguous Removal or Item Reference

### Goal
Verify ambiguous removal asks for clarification.

### Steps
1. Start a voice session.
2. Say: “Add one chicken taco with no onions.”
3. Say: “Add one chicken taco with extra salsa.”
4. Say: “Remove the chicken taco.”
5. Verify the agent asks which one.
6. Say: “Remove the one with no onions.”
7. Verify only that line item is removed.

### Expected Result
The system asks for clarification and does not mutate order state until the caller clarifies.

### Troubleshooting
If the wrong taco is removed before clarification, removal logic and dialogue state are incorrect.
