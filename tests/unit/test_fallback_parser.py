"""Unit tests for the deterministic fallback parser.

Every test exercises ``parse_fallback_intent`` directly — no Anthropic
calls are made.
"""

from restaurant_agent.fallback_parser import parse_fallback_intent


# ── Menu search ─────────────────────────────────────────────────────────


def test_menu_search_by_item_name():
    res = parse_fallback_intent("What tacos do you have?")
    assert res.tool_name == "search_menu"
    assert res.safe_to_execute is True


def test_menu_search_tacos_only_phrase():
    res = parse_fallback_intent("Tacos.")
    assert res.tool_name == "search_menu"
    assert res.safe_to_execute is True


def test_menu_search_generic():
    res = parse_fallback_intent("Show me the menu")
    assert res.tool_name == "search_menu"
    assert res.safe_to_execute is True


def test_menu_search_vegetarian_listing():
    res = parse_fallback_intent("what kind of vegetarian items do you have")
    assert res.tool_name == "search_menu"
    assert res.safe_to_execute is True


# ── Add item ────────────────────────────────────────────────────────────


def test_add_two_chicken_tacos_with_no_onions():
    res = parse_fallback_intent(
        "Add two chicken tacos with no onions",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "add_order_item"
    assert res.tool_name == "add_order_item"
    assert res.arguments["item_id"] == "chicken_tacos"
    assert res.arguments["quantity"] == 2
    assert "no onions" in res.arguments["special_instructions"]
    assert res.safe_to_execute is True


def test_quantity_two_parsed():
    res = parse_fallback_intent(
        "I'd like two chicken tacos",
        session_context={"session_id": "sess_test"},
    )
    assert res.arguments["quantity"] == 2


def test_could_i_get_two_chicken_tacos():
    res = parse_fallback_intent(
        "could I get two chicken tacos",
        session_context={"session_id": "sess_test"},
    )
    assert res.tool_name == "add_order_item"
    assert res.arguments["item_id"] == "chicken_tacos"
    assert res.arguments["quantity"] == 2
    assert res.safe_to_execute is True


def test_can_i_have_a_lemonade():
    res = parse_fallback_intent(
        "can I have a lemonade",
        session_context={"session_id": "sess_test"},
    )
    assert res.tool_name == "add_order_item"
    assert res.arguments["item_id"] == "lemonade"
    assert res.arguments["quantity"] == 1
    assert res.safe_to_execute is True


def test_one_horchata_please():
    res = parse_fallback_intent(
        "one horchata please",
        session_context={"session_id": "sess_test"},
    )
    assert res.tool_name == "add_order_item"
    assert res.arguments["item_id"] == "horchata"
    assert res.arguments["quantity"] == 1
    assert res.safe_to_execute is True


def test_chicken_tacos_maps_to_id():
    res = parse_fallback_intent(
        "Add a chicken taco",
        session_context={"session_id": "sess_test"},
    )
    assert res.arguments["item_id"] == "chicken_tacos"


def test_no_onions_becomes_special_instruction():
    res = parse_fallback_intent(
        "Add one chicken taco no onions",
        session_context={"session_id": "sess_test"},
    )
    assert "no onions" in res.arguments.get("special_instructions", [])


def test_extra_queso_not_safe_to_execute():
    res = parse_fallback_intent(
        "Add one chicken taco with extra queso",
        session_context={"session_id": "sess_test"},
    )
    assert res.safe_to_execute is False
    assert res.clarification_question is not None
    assert "extra queso" in res.clarification_question.lower()


def test_natural_phrase_with_special_instruction_is_safe():
    res = parse_fallback_intent(
        "I'd like two chicken tacos with no onions",
        session_context={"session_id": "sess_test"},
    )
    assert res.tool_name == "add_order_item"
    assert res.arguments["quantity"] == 2
    assert "no onions" in res.arguments["special_instructions"]
    assert res.safe_to_execute is True


def test_lobster_pizza_does_not_add_unknown_item():
    res = parse_fallback_intent(
        "could I get lobster pizza",
        session_context={"session_id": "sess_test"},
    )
    assert res.safe_to_execute is False
    assert res.tool_name is None
    assert res.clarification_question is not None


def test_broad_add_request_is_not_safe_to_execute():
    res = parse_fallback_intent("give me all of it")
    assert res.intent == "broad_add_request"
    assert res.tool_name is None
    assert res.safe_to_execute is False
    assert res.clarification_question is not None


# ── Compute total ───────────────────────────────────────────────────────


def test_what_is_my_total():
    res = parse_fallback_intent(
        "What is my total?",
        session_context={"session_id": "sess_test"},
    )
    assert res.tool_name == "compute_total"
    assert res.safe_to_execute is True


# ── Order summary / readback ────────────────────────────────────────────


def test_read_back_my_order():
    res = parse_fallback_intent(
        "Read back my order",
        session_context={"session_id": "sess_test"},
    )
    assert res.tool_name == "get_order_summary"
    assert res.safe_to_execute is True


# ── Cancel ──────────────────────────────────────────────────────────────


def test_cancel_my_order():
    res = parse_fallback_intent(
        "Cancel my order",
        session_context={"session_id": "sess_test"},
    )
    assert res.tool_name == "cancel_order"
    assert res.safe_to_execute is True


# ── Remove without line_item_id ─────────────────────────────────────────


def test_remove_without_line_item_id_not_safe():
    res = parse_fallback_intent(
        "Remove the chicken taco",
        session_context={"session_id": "sess_test"},
    )
    assert res.safe_to_execute is False
    assert res.clarification_question is not None


# ── Payment refusal ─────────────────────────────────────────────────────


def test_payment_request_refused():
    res = parse_fallback_intent("Can I pay with my credit card?")
    assert res.safe_to_execute is False
    assert res.tool_name is None
    assert res.response_text is not None
    assert "pay" in res.response_text.lower() or "payment" in res.response_text.lower()


# ── Ambiguous utterance ─────────────────────────────────────────────────


def test_ambiguous_utterance():
    res = parse_fallback_intent("hmm okay thanks")
    assert res.safe_to_execute is False
    assert res.clarification_question is not None


# ── Allergy guarantee ───────────────────────────────────────────────────


def test_allergy_guarantee_does_not_guarantee():
    res = parse_fallback_intent(
        "Can you guarantee the black bean bowl is safe for peanut allergy?"
    )
    assert res.safe_to_execute is False
    assert (
        "guarantee" in (res.response_text or "").lower()
        or "cannot" in (res.response_text or "").lower()
    )
    # Must NOT claim it's safe
    assert res.tool_name is None


# ── Confirm ─────────────────────────────────────────────────────────────


def test_confirm_order():
    res = parse_fallback_intent(
        "Yes, confirm the order",
        session_context={"session_id": "sess_test"},
    )
    assert res.tool_name == "confirm_order"
    assert res.safe_to_execute is True


def test_conversation_done_phrase():
    res = parse_fallback_intent(
        "that's it",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "conversation_done"
    assert res.safe_to_execute is True


# ── Customer name ───────────────────────────────────────────────────────


def test_customer_name_capture():
    res = parse_fallback_intent("Put the order under Fernando")
    assert res.intent == "set_customer_name"
    assert res.arguments["customer_name"] == "Fernando"
    assert res.safe_to_execute is True
