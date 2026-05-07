# Restaurant Voice Ordering Agent User Stories

This document defines the manual walkthrough stories for the Restaurant Voice Ordering Agent. Each story has a stable ID, acceptance criteria, manual walkthrough steps, expected observable outcomes, a reference screenshot path, and a matching automated user-story test.

The primary production interface is the Twilio-compatible phone voice interface. For reproducible local grading, the TA can use the browser voice interface. Both interfaces use the same backend agent orchestrator, MCP tools, RAG index, order state, pricing logic, and structured logging.

The browser voice interface shall support spoken user input and spoken agent responses. Typed input may be used only as fallback, debugging, or accessibility support.

## Manual Walkthrough Setup

1. Start the application through Docker Compose.
2. Open the browser voice interface at `http://localhost:8000`.
3. Click `Start Voice Order`.
4. Allow microphone permission if prompted.
5. Follow each story using the sample utterances.
6. Verify the transcript panel, order panel, total panel, status messages, and spoken responses.

The application shall also expose Twilio-compatible phone routes, but these stories do not require a live Twilio phone call.

## Optional Phone Path Validation

If Twilio credentials and a public webhook URL are configured, the TA may validate the same ordering behaviors through the Twilio phone interface. The phone path shall use the same backend agent, MCP tools, RAG index, order state, pricing logic, and structured logging as the browser voice interface.

Phone sessions can be inspected through structured logs, `GET /api/debug/sessions/recent`, and `GET /api/debug/session/{session_id}`.

## US-01: Start a Browser Voice Call and Receive Greeting

**User Story:**
As a restaurant caller, I want to start a voice ordering session so that I can speak with the automated ordering agent.

**Acceptance Criteria:**
Given the application is running through Docker Compose
When the caller opens the browser voice interface and starts a voice order
Then the system creates a new session, greets the caller aloud, and displays the session transcript.

**Manual Walkthrough Steps:**
1. Open `http://localhost:8000`.
2. Click `Start Voice Order`.
3. Allow microphone permission if prompted.
4. Verify that the agent speaks a greeting aloud.
5. Verify that the transcript panel shows the greeting.
6. Verify that the order panel is empty.
7. Verify that the total is `$0.00`.

**Expected Observable Outcome:**
The agent says: “Welcome to the restaurant voice ordering assistant. I can answer menu questions and help take your order. What would you like today?”

The page displays:
- active session status
- transcript panel
- empty order panel
- total of `$0.00`

**Reference Screenshot:**
`docs/assets/stories/us_01_expected.png`

**Related Automated Test:**
`tests/user_stories/test_us_01_start_voice_call.py`

## US-02: Ask a Menu Question Using RAG

**User Story:**
As a restaurant caller, I want to ask what items are on the menu so that I can decide what to order.

**Acceptance Criteria:**
Given a voice session is active
When the caller asks a menu question
Then the agent searches the RAG menu index and answers using grounded menu evidence.

**Manual Walkthrough Steps:**
1. Start a voice order session.
2. Say: “What tacos do you have?”
3. Verify that the agent responds with taco menu items from the indexed menu.
4. Verify that the response does not include items that are not in the menu.
5. Verify that the transcript shows the caller question and agent response.
6. Verify that the order remains empty.

**Expected Observable Outcome:**
The agent lists available taco items from the sample restaurant menu, including names and prices when available.

**Reference Screenshot:**
`docs/assets/stories/us_02_expected.png`

**Related Automated Test:**
`tests/user_stories/test_us_02_menu_question_rag.py`

## US-03: Ask a Dietary or Allergen Question

**User Story:**
As a restaurant caller with dietary preferences or restrictions, I want to ask about menu items so that I can make an informed choice.

**Acceptance Criteria:**
Given a voice session is active
When the caller asks about a dietary restriction or allergen
Then the agent uses menu metadata, explicit menu evidence, and conservative dietary rules to answer without making unsupported safety claims.

**Manual Walkthrough Steps:**
1. Start a voice order session.
2. Say: “Do you have anything vegetarian?”
3. Verify that the agent lists items that are explicitly marked vegetarian or appear vegetarian based on menu evidence.
4. Say: “Is the black bean bowl safe for a peanut allergy?”
5. Verify that the agent does not guarantee allergy safety unless explicit menu evidence supports it.
6. Verify that the transcript includes cautious wording.
7. Verify that the order remains empty unless the caller explicitly orders an item.

**Expected Observable Outcome:**
The agent gives a cautious, grounded response similar to:
“The black bean bowl is listed without meat ingredients and may be a vegetarian option. For peanut allergies, the menu does not list peanuts for that item, but I cannot guarantee it is peanut-free.”

**Reference Screenshot:**
`docs/assets/stories/us_03_expected.png`

**Related Automated Test:**
`tests/user_stories/test_us_03_dietary_question.py`

## US-04: Add an Item with Quantity and Modification

**User Story:**
As a restaurant caller, I want to order an item with a quantity and modification so that the order reflects what I actually want.

**Acceptance Criteria:**
Given a voice session is active
When the caller asks to add a menu item with quantity and modification
Then the agent calls MCP order tools, adds the item, stores the modification, and updates the running total.

**Manual Walkthrough Steps:**
1. Start a voice order session.
2. Say: “Add two chicken tacos with no onions.”
3. Verify that the order panel shows `Chicken Tacos`.
4. Verify that the quantity is `2`.
5. Verify that the modification `no onions` appears on the line item.
6. Verify that the running total is greater than `$0.00`.
7. Verify that the agent confirms the item was added aloud.

**Expected Observable Outcome:**
The agent says something similar to:
“Added two chicken tacos with no onions. Your current total is $X.XX.”

The order panel shows:
- Chicken Tacos
- quantity 2
- modification: no onions
- updated subtotal, tax, and total

**Reference Screenshot:**
`docs/assets/stories/us_04_expected.png`

**Related Automated Test:**
`tests/user_stories/test_us_04_add_item_with_modification.py`

## US-05: Add an Unsupported Modification as a Special Instruction

**User Story:**
As a restaurant caller, I want to request a special modification even if it is not a priced menu option so that the restaurant can see my request.

**Acceptance Criteria:**
Given a voice session is active and an item is being added or updated
When the caller requests a modification that is not a known priced option
Then the agent asks whether to save it as an unpriced special instruction and does not invent a price.

**Manual Walkthrough Steps:**
1. Start a voice order session.
2. Say: “Add one chicken taco with extra queso.”
3. Verify that the agent says `extra queso` is not listed as a priced option.
4. Verify that the agent asks whether to include it as a special instruction.
5. Say: “Yes.”
6. Verify that the order panel shows `extra queso` as a special instruction.
7. Verify that no invented price is added for `extra queso`.

**Expected Observable Outcome:**
The agent says something similar to:
“I do not see extra queso as a priced option. I can add it as a special instruction at no extra charge, but the restaurant may not guarantee it. Should I include that note?”

After the caller says yes, the order shows:
- Chicken Taco
- special instruction: extra queso
- price based only on canonical item price and known priced modifications

**Reference Screenshot:**
`docs/assets/stories/us_05_expected.png`

**Related Automated Test:**
`tests/user_stories/test_us_05_special_instruction.py`

## US-06: Remove or Update an Item

**User Story:**
As a restaurant caller, I want to change my order so that mistakes or changes of mind can be corrected before confirmation.

**Acceptance Criteria:**
Given the caller has at least one item in the order
When the caller removes or updates an item
Then the agent calls the appropriate MCP tool, updates order state, and recomputes the total.

**Manual Walkthrough Steps:**
1. Start a voice order session.
2. Say: “Add two chicken tacos.”
3. Verify that two chicken tacos appear in the order.
4. Say: “Change that to one chicken taco.”
5. Verify that the quantity changes from `2` to `1`.
6. Verify that the total decreases.
7. Say: “Remove the chicken taco.”
8. Verify that the order becomes empty.
9. Verify that the total returns to `$0.00`.

**Expected Observable Outcome:**
The agent confirms the update and removal aloud. The order state updates after each step.

**Reference Screenshot:**
`docs/assets/stories/us_06_expected.png`

**Related Automated Test:**
`tests/user_stories/test_us_06_remove_or_update_item.py`

## US-07: Ask for Order Summary and Running Total

**User Story:**
As a restaurant caller, I want to hear my current order and total so that I can review it before confirming.

**Acceptance Criteria:**
Given the caller has items in the order
When the caller asks for a summary or total
Then the agent reads back the current order and computes the total through the MCP total tool.

**Manual Walkthrough Steps:**
1. Start a voice order session.
2. Say: “Add one chicken taco with no onions.”
3. Say: “Add one lemonade.”
4. Say: “What is my total?”
5. Verify that the agent reads the current total aloud.
6. Say: “Read back my order.”
7. Verify that the agent reads item names, quantities, modifications, subtotal, tax, and total.

**Expected Observable Outcome:**
The agent gives a spoken summary similar to:
“Your order is one chicken taco with no onions and one lemonade. Your subtotal is $X.XX, tax is $X.XX, and your total is $X.XX.”

**Reference Screenshot:**
`docs/assets/stories/us_07_expected.png`

**Related Automated Test:**
`tests/user_stories/test_us_07_summary_and_total.py`

## US-08: Provide Customer Name and Confirm Order

**User Story:**
As a restaurant caller, I want to place the order under my name and confirm it only after hearing the readback.

**Acceptance Criteria:**
Given the caller has at least one item in the order
When the caller provides a name and confirms after readback
Then the system stores the customer name, computes the final total, confirms the order, and returns a confirmation ID.

**Manual Walkthrough Steps:**
1. Start a voice order session.
2. Say: “Add one chicken taco with no onions.”
3. Say: “Put the order under Fernando.”
4. Say: “That is everything.”
5. Verify that the agent reads back the order, customer name, subtotal, tax, and total.
6. When the agent asks for confirmation, say: “Yes, confirm.”
7. Verify that the order status changes to confirmed.
8. Verify that the system displays a confirmation ID.

**Expected Observable Outcome:**
The agent says something similar to:
“Your order is confirmed under Fernando. Your confirmation number is ABC123.”

The UI shows:
- customer name: Fernando
- order status: confirmed
- confirmation ID
- final total

**Reference Screenshot:**
`docs/assets/stories/us_08_expected.png`

**Related Automated Test:**
`tests/user_stories/test_us_08_name_and_confirm.py`

## US-09: Error Path — Unknown Menu Item

**User Story:**
As a restaurant caller, I want the agent to tell me when an item is not on the menu so that I do not accidentally order something unavailable.

**Acceptance Criteria:**
Given a voice session is active
When the caller requests an item that is not in the indexed menu
Then the agent does not add the item and asks the caller to choose an available menu item.

**Manual Walkthrough Steps:**
1. Start a voice order session.
2. Say: “Add one lobster pizza.”
3. Verify that the agent says it cannot find `lobster pizza` on the menu.
4. Verify that no item is added to the order.
5. Verify that the total remains `$0.00`.

**Expected Observable Outcome:**
The agent says something similar to:
“I could not find lobster pizza on this menu. Would you like to choose something from the available menu items?”

The order remains empty.

**Reference Screenshot:**
`docs/assets/stories/us_09_expected.png`

**Related Automated Test:**
`tests/user_stories/test_us_09_unknown_menu_item.py`

## US-10: Error Path — Ambiguous Removal or Item Reference

**User Story:**
As a restaurant caller, I want the agent to ask for clarification when my request could refer to more than one item so that it does not remove or change the wrong thing.

**Acceptance Criteria:**
Given the caller has multiple similar items or line items in the order
When the caller makes an ambiguous reference
Then the agent asks a clarification question and does not mutate order state until the caller answers.

**Manual Walkthrough Steps:**
1. Start a voice order session.
2. Say: “Add one chicken taco with no onions.”
3. Say: “Add one chicken taco with extra salsa.”
4. Say: “Remove the chicken taco.”
5. Verify that the agent asks which chicken taco line item to remove.
6. Verify that both line items remain in the order before clarification.
7. Say: “Remove the one with no onions.”
8. Verify that only the no-onions line item is removed.
9. Verify that the extra-salsa line item remains.
10. Verify that the total is recomputed.

**Expected Observable Outcome:**
The agent says something similar to:
“You have two chicken taco entries: one with no onions and one with extra salsa. Which one should I remove?”

No order mutation occurs until the caller clarifies.

**Reference Screenshot:**
`docs/assets/stories/us_10_expected.png`

**Related Automated Test:**
`tests/user_stories/test_us_10_ambiguous_removal.py`
