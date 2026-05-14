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


def test_fish_tacos_and_burger_routes_to_multi_add():
    res = parse_fallback_intent(
        "the fish tacos and a burger",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "add_multiple_items"
    assert res.safe_to_execute is True
    item_ids = [item["item_id"] for item in res.arguments["items"]]
    assert item_ids == ["crispy_fish_tacos", "classic_burger"]


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
    assert res.arguments["item_id"] == "chicken_tacos"
    assert res.arguments["quantity"] == 1
    assert res.arguments["known_modification_names"] == []
    assert res.arguments["special_instructions"] == ["extra queso"]


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
    assert "don't see lobster pizza on the menu" in res.clarification_question.lower()


def test_broad_add_request_is_not_safe_to_execute():
    res = parse_fallback_intent("give me all of it")
    assert res.intent == "broad_add_request"
    assert res.tool_name is None
    assert res.safe_to_execute is False
    assert res.clarification_question is not None


def test_broad_add_request_with_that_variant():
    res = parse_fallback_intent("give me all of that")
    assert res.intent == "broad_add_request"
    assert res.safe_to_execute is False


def test_broad_add_request_with_those_variant():
    res = parse_fallback_intent("give me all of those")
    assert res.intent == "broad_add_request"
    assert res.safe_to_execute is False


def test_broad_add_request_all_of_them():
    res = parse_fallback_intent("all of them")
    assert res.intent == "broad_add_request"
    assert res.safe_to_execute is False


def test_broad_add_request_one_of_each_of_those():
    res = parse_fallback_intent("give me one of each of those")
    assert res.intent == "broad_add_request"
    assert res.safe_to_execute is False


# ── Compute total ───────────────────────────────────────────────────────


def test_what_is_my_total():
    res = parse_fallback_intent(
        "What is my total?",
        session_context={"session_id": "sess_test"},
    )
    assert res.tool_name == "compute_total"
    assert res.safe_to_execute is True


def test_how_much_is_veggie_quesadilla():
    res = parse_fallback_intent("how much is the veggie quesadilla")
    assert res.intent == "price_lookup"
    assert res.arguments["item_id"] == "veggie_quesadilla"
    assert res.safe_to_execute is True


def test_how_much_is_lemonade():
    res = parse_fallback_intent("how much is lemonade")
    assert res.intent == "price_lookup"
    assert res.arguments["item_id"] == "lemonade"
    assert res.safe_to_execute is True


def test_how_much_is_quesadilla_alias():
    res = parse_fallback_intent("how much is the quesadilla")
    assert res.intent == "price_lookup"
    assert res.arguments["item_id"] == "veggie_quesadilla"


def test_how_much_is_burrito_alias():
    res = parse_fallback_intent("what does the burrito cost")
    assert res.intent == "price_lookup"
    assert res.arguments["item_id"] == "carnitas_burrito"


def test_pronoun_followup_uses_last_mentioned_item():
    res = parse_fallback_intent(
        "I'll take one of those",
        session_context={
            "session_id": "sess_test",
            "last_mentioned_item_id": "veggie_quesadilla",
        },
    )
    assert res.intent == "add_order_item"
    assert res.arguments["item_id"] == "veggie_quesadilla"
    assert res.arguments["quantity"] == 1


def test_pronoun_followup_handles_ill_take_variant():
    res = parse_fallback_intent(
        "Ill take one of those.",
        session_context={
            "session_id": "sess_test",
            "last_mentioned_item_id": "veggie_quesadilla",
        },
    )
    assert res.intent == "add_order_item"
    assert res.arguments["item_id"] == "veggie_quesadilla"
    assert res.arguments["quantity"] == 1


def test_pronoun_followup_handles_one_of_those_variant():
    res = parse_fallback_intent(
        "one of those.",
        session_context={
            "session_id": "sess_test",
            "last_mentioned_item_id": "veggie_quesadilla",
        },
    )
    assert res.intent == "add_order_item"
    assert res.arguments["item_id"] == "veggie_quesadilla"


def test_pronoun_followup_handles_i_will_take_variant():
    res = parse_fallback_intent(
        "I will take one of those",
        session_context={
            "session_id": "sess_test",
            "last_mentioned_item_id": "veggie_quesadilla",
        },
    )
    assert res.intent == "add_order_item"
    assert res.arguments["item_id"] == "veggie_quesadilla"


def test_pronoun_followup_handles_please_variant():
    res = parse_fallback_intent(
        "I'll take one of those please",
        session_context={
            "session_id": "sess_test",
            "last_mentioned_item_id": "veggie_quesadilla",
        },
    )
    assert res.intent == "add_order_item"
    assert res.arguments["item_id"] == "veggie_quesadilla"


def test_pronoun_followup_handles_take_it_variant():
    res = parse_fallback_intent(
        "I'll take it",
        session_context={
            "session_id": "sess_test",
            "last_mentioned_item_id": "veggie_quesadilla",
        },
    )
    assert res.intent == "add_order_item"
    assert res.arguments["item_id"] == "veggie_quesadilla"


def test_pronoun_followup_handles_numeric_one_variant():
    res = parse_fallback_intent(
        "I'll take 1 of those.",
        session_context={
            "session_id": "sess_test",
            "last_mentioned_item_id": "veggie_quesadilla",
        },
    )
    assert res.intent == "add_order_item"
    assert res.arguments["item_id"] == "veggie_quesadilla"
    assert res.arguments["quantity"] == 1


def test_pronoun_followup_handles_numeric_two_variant():
    res = parse_fallback_intent(
        "give me 2 of those",
        session_context={
            "session_id": "sess_test",
            "last_mentioned_item_id": "veggie_quesadilla",
        },
    )
    assert res.intent == "add_order_item"
    assert res.arguments["item_id"] == "veggie_quesadilla"
    assert res.arguments["quantity"] == 2


def test_multi_item_add_handles_ill_take_fish_tacos_and_burger():
    res = parse_fallback_intent(
        "Ill take the fish tacos and a burger.",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "add_multiple_items"
    assert res.safe_to_execute is True
    item_ids = [item["item_id"] for item in res.arguments["items"]]
    assert item_ids == ["crispy_fish_tacos", "classic_burger"]


def test_remove_by_name_routes_when_item_is_identified():
    res = parse_fallback_intent(
        "remove the quesadilla",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "remove_order_item_by_name"
    assert res.arguments["item_id"] == "veggie_quesadilla"


def test_cancel_the_burger_routes_to_remove_by_name():
    res = parse_fallback_intent(
        "cancel the burger",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "remove_order_item_by_name"
    assert res.arguments["item_id"] == "classic_burger"


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
    assert res.safe_to_execute is True
    assert res.intent == "remove_order_item_by_name"
    assert res.arguments["item_id"] == "chicken_tacos"


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


def test_confirm_my_order():
    res = parse_fallback_intent(
        "confirm my order",
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


def test_no_thats_all_phrase():
    res = parse_fallback_intent(
        "no that's all",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "conversation_done"
    assert res.safe_to_execute is True


def test_okay_thats_all_phrase():
    res = parse_fallback_intent(
        "okay that's all",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "conversation_done"
    assert res.safe_to_execute is True


def test_im_ready_to_proceed_phrase():
    res = parse_fallback_intent(
        "I'm ready to proceed",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "conversation_done"
    assert res.safe_to_execute is True


def test_im_done_ordering_phrase():
    res = parse_fallback_intent(
        "I'm done ordering",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "conversation_done"
    assert res.safe_to_execute is True


def test_finish_order_phrase_is_conversation_done():
    res = parse_fallback_intent(
        "finish order",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "conversation_done"
    assert res.tool_name is None


def test_complete_order_phrase_is_conversation_done():
    res = parse_fallback_intent(
        "complete order",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "conversation_done"
    assert res.tool_name is None


def test_checkout_phrase_is_conversation_done():
    res = parse_fallback_intent(
        "checkout",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "conversation_done"
    assert res.tool_name is None


# ── Customer name ───────────────────────────────────────────────────────


def test_customer_name_capture():
    res = parse_fallback_intent("Put the order under Fernando")
    assert res.intent == "set_customer_name"
    assert res.arguments["customer_name"] == "Fernando"


def test_customer_name_capture_under_the_name():
    res = parse_fallback_intent("Put it under the name Fernando")
    assert res.intent == "set_customer_name"
    assert res.arguments["customer_name"] == "Fernando"


def test_customer_name_capture_its_fernando():
    res = parse_fallback_intent("It's Fernando")
    assert res.intent == "set_customer_name"
    assert res.arguments["customer_name"] == "Fernando"


def test_bare_name_capture_trims_trailing_punctuation():
    res = parse_fallback_intent(
        "Fernando.",
        session_context={
            "session_id": "sess_test",
            "pending_action": "collect_customer_name",
        },
    )
    assert res.intent == "set_customer_name"
    assert res.arguments["customer_name"] == "Fernando"


def test_bare_name_capture_when_collecting_name():
    res = parse_fallback_intent(
        "Fernando",
        session_context={"pending_action": "collect_customer_name"},
    )
    assert res.intent == "set_customer_name"
    assert res.arguments["customer_name"] == "Fernando"


def test_multi_item_add_burrito_and_burger():
    res = parse_fallback_intent(
        "Give me a Burrito and a Burger",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "add_multiple_items"
    assert res.safe_to_execute is True
    item_ids = [item["item_id"] for item in res.arguments["items"]]
    assert item_ids == ["carnitas_burrito", "classic_burger"]


def test_multi_item_add_two_drinks():
    res = parse_fallback_intent(
        "add a lemonade and a horchata",
        session_context={"session_id": "sess_test"},
    )
    assert res.intent == "add_multiple_items"
    assert res.safe_to_execute is True
    item_ids = [item["item_id"] for item in res.arguments["items"]]
    assert item_ids == ["lemonade", "horchata"]


def test_bare_item_followup_after_menu_list():
    res = parse_fallback_intent(
        "The Carnitas Burritos",
        session_context={
            "session_id": "sess_test",
            "last_intent": "search_menu",
            "last_agent_response": "Our meat options are Chicken Tacos and Carnitas Burrito.",
        },
    )
    assert res.intent == "add_order_item"
    assert res.arguments["item_id"] == "carnitas_burrito"
    assert res.safe_to_execute is True
