import pytest
from starlette.requests import Request

from restaurant_agent.api import api_create_session, api_turn
from restaurant_agent.schemas import AgentTurnRequest, CreateSessionRequest
from restaurant_agent.session_store import get_session


def _request(request_id: str) -> Request:
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api",
            "raw_path": b"/api",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive=None,
    )
    request.state.request_id = request_id
    return request


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_start_session_returns_greeting() -> None:
    response = api_create_session(
        _request("req-start-session"),
        CreateSessionRequest(channel="browser"),
    )
    data = response.model_dump()
    assert data["session_id"]
    assert "Welcome" in data["agent_text"]
    assert data["request_id"]


def test_turn_menu_question_rag() -> None:
    sess = api_create_session(
        _request("req-turn-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-turn-menu"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="What tacos do you have?",
            channel="browser",
            metadata={},
        ),
    )
    data = response.model_dump()
    assert data["intent"] == "search_menu"
    assert len(data["tool_calls"]) > 0
    assert data["tool_calls"][0]["tool_name"] == "search_menu"
    assert data["tool_calls"][0]["status"] == "success"
    assert "taco" in data["agent_text"].lower()
    assert "street corn" not in data["agent_text"].lower()
    assert "black bean bowl" not in data["agent_text"].lower()


def test_turn_add_chicken_tacos_updates_order() -> None:
    sess = api_create_session(
        _request("req-add-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-add-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add two chicken tacos",
            channel="browser",
            metadata={},
        ),
    )
    data = response.model_dump()
    assert data["intent"] == "add_order_item"
    assert data["order"]["items"][0]["item_id"] == "chicken_tacos"
    assert data["order"]["items"][0]["quantity"] == 2
    assert "would you like anything else" in data["agent_text"].lower()


def test_turn_natural_phrase_adds_item() -> None:
    sess = api_create_session(
        _request("req-natural-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-natural-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="could I get two chicken tacos with no onions",
            channel="browser",
            metadata={},
        ),
    )
    data = response.model_dump()
    assert data["intent"] == "add_order_item"
    assert data["order"]["items"][0]["quantity"] == 2
    assert "no onions" in data["order"]["items"][0]["special_instructions"]


def test_broad_add_requires_confirmation_before_mutation() -> None:
    sess = api_create_session(
        _request("req-broad-add-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    list_response = api_turn(
        _request("req-broad-add-list"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="what kind of vegetarian items do you have",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert list_response["intent"] == "search_menu"

    broad_response = api_turn(
        _request("req-broad-add-ask"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="give me all of that",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert broad_response["intent"] == "broad_add_request"
    assert len(broad_response["order"]["items"]) == 0
    assert "just to confirm" in broad_response["agent_text"].lower()
    assert "black bean bowl" in broad_response["agent_text"].lower()
    assert "veggie quesadilla" in broad_response["agent_text"].lower()

    confirm_response = api_turn(
        _request("req-broad-add-confirm"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="yes",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    item_ids = {item["item_id"] for item in confirm_response["order"]["items"]}
    assert {
        "black_bean_bowl",
        "veggie_quesadilla",
        "street_corn",
        "chips_and_salsa",
        "lemonade",
        "horchata",
    }.issubset(item_ids)
    assert "would you like anything else" in confirm_response["agent_text"].lower()
    assert any(
        tool_call["tool_name"] == "add_order_item"
        for tool_call in confirm_response["tool_calls"]
    )


def test_pending_add_all_allows_price_lookup_before_confirmation() -> None:
    sess = api_create_session(
        _request("req-pending-price-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-pending-price-list"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="what kind of vegetarian items do you have",
            channel="browser",
            metadata={},
        ),
    )
    api_turn(
        _request("req-pending-price-broad"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="all of them",
            channel="browser",
            metadata={},
        ),
    )

    price_response = api_turn(
        _request("req-pending-price-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="how much is the quesadilla",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert price_response["intent"] == "price_lookup"
    assert "9.00" in price_response["agent_text"]
    assert len(price_response["order"]["items"]) == 0

    confirm_response = api_turn(
        _request("req-pending-price-yes"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="yes",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert len(confirm_response["order"]["items"]) >= 2
    assert "would you like anything else" in confirm_response["agent_text"].lower()


def test_broad_add_decline_does_not_change_order() -> None:
    sess = api_create_session(
        _request("req-broad-decline-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-broad-decline-list"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="what kind of vegetarian items do you have",
            channel="browser",
            metadata={},
        ),
    )

    api_turn(
        _request("req-broad-decline-ask"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="give me all of those",
            channel="browser",
            metadata={},
        ),
    )

    decline_response = api_turn(
        _request("req-broad-decline-no"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="no",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert len(decline_response["order"]["items"]) == 0
    assert "won't add those items" in decline_response["agent_text"].lower()


def test_broad_add_without_prior_listing_asks_clarification() -> None:
    sess = api_create_session(
        _request("req-broad-no-list-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-broad-no-list-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="I want every single item",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert len(response["order"]["items"]) == 0
    assert "which items would you like me to add" in response["agent_text"].lower()


def test_multi_item_add_burrito_and_burger() -> None:
    sess = api_create_session(
        _request("req-multi-add-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-multi-add-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Give me a Burrito and a Burger",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    item_ids = [item["item_id"] for item in response["order"]["items"]]
    assert "carnitas_burrito" in item_ids
    assert "classic_burger" in item_ids


def test_multi_item_add_two_drinks() -> None:
    sess = api_create_session(
        _request("req-multi-drink-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-multi-drink-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="add a lemonade and a horchata",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    item_ids = [item["item_id"] for item in response["order"]["items"]]
    assert item_ids == ["lemonade", "horchata"]


def test_multi_item_add_fish_tacos_and_burger() -> None:
    sess = api_create_session(
        _request("req-fish-burger-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-fish-burger-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="the fish tacos and a burger",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    item_ids = [item["item_id"] for item in response["order"]["items"]]
    assert item_ids == ["crispy_fish_tacos", "classic_burger"]
    assert "would you like anything else" in response["agent_text"].lower()


def test_turn_unsupported_modification_asks_clarification() -> None:
    sess = api_create_session(
        _request("req-mod-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-mod-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco with extra queso",
            channel="browser",
            metadata={},
        ),
    )
    data = response.model_dump()
    assert len(data["order"]["items"]) == 0
    assert "extra queso" in data["agent_text"].lower()
    session = get_session(session_id)
    assert session is not None
    assert session.pending_action == "confirm_add_special_instruction"
    assert session.pending_context["arguments"]["item_id"] == "chicken_tacos"
    assert session.pending_context["arguments"]["quantity"] == 1
    assert session.pending_context["arguments"]["known_modification_names"] == []
    assert session.pending_context["arguments"]["special_instructions"] == [
        "extra queso"
    ]


def test_turn_unsupported_modification_yes_adds_special_instruction() -> None:
    sess = api_create_session(
        _request("req-mod-confirm-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-mod-confirm-start"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco with extra queso",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-mod-confirm-yes"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="yes",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["items"][0]["item_id"] == "chicken_tacos"
    assert response["order"]["items"][0]["special_instructions"] == ["extra queso"]
    assert response["order"]["items"][0]["known_modifications"] == []
    assert response["order"]["subtotal"] == 8.50
    assert response["order"]["tax"] == 0.70
    assert response["order"]["total"] == 9.20
    assert response["tool_calls"][0]["tool_name"] == "add_order_item"
    assert "special instruction" in response["agent_text"].lower()
    session = get_session(session_id)
    assert session is not None
    assert session.pending_action is None


def test_turn_unsupported_modification_no_clears_pending_without_adding() -> None:
    sess = api_create_session(
        _request("req-mod-decline-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-mod-decline-start"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco with extra queso",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-mod-decline-no"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="no",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["items"] == []
    assert "won't add" in response["agent_text"].lower()
    session = get_session(session_id)
    assert session is not None
    assert session.pending_action is None


def test_turn_unknown_menu_item_returns_clear_not_found_response() -> None:
    sess = api_create_session(
        _request("req-unknown-item-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-unknown-item-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one lobster pizza",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["items"] == []
    assert "don't see lobster pizza on the menu" in response["agent_text"].lower()
    assert "not sure which item" not in response["agent_text"].lower()


def test_turn_ambiguous_remove_followup_removes_instead_of_adding() -> None:
    sess = api_create_session(
        _request("req-remove-clarify-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-remove-clarify-add1"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add chicken taco",
            channel="browser",
            metadata={},
        ),
    )
    api_turn(
        _request("req-remove-clarify-add2"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add fish taco",
            channel="browser",
            metadata={},
        ),
    )

    clarify = api_turn(
        _request("req-remove-clarify-remove"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="remove the taco",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert len(clarify["order"]["items"]) == 2
    assert "which item would you like to remove" in clarify["agent_text"].lower()

    followup = api_turn(
        _request("req-remove-clarify-fish"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="fish taco",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert [item["item_id"] for item in followup["order"]["items"]] == ["chicken_tacos"]
    assert followup["tool_calls"][0]["tool_name"] == "remove_order_item"
    assert "removed" in followup["agent_text"].lower()


def test_turn_total_request_returns_total() -> None:
    sess = api_create_session(
        _request("req-total-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-total-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add two chicken tacos",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-total-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="What is my total?",
            channel="browser",
            metadata={},
        ),
    )
    data = response.model_dump()
    assert data["intent"] == "compute_total"
    assert "total" in data["agent_text"].lower()


def test_price_lookup_returns_canonical_item_price() -> None:
    sess = api_create_session(
        _request("req-price-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-price-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="how much is the veggie quesadilla",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["intent"] == "price_lookup"
    assert "9.00" in response["agent_text"]
    assert "unavailable" not in response["agent_text"].lower()
    assert len(response["order"]["items"]) == 0


def test_price_lookup_works_for_lemonade() -> None:
    sess = api_create_session(
        _request("req-price-drink-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-price-drink-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="how much is lemonade",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["intent"] == "price_lookup"
    assert "3.00" in response["agent_text"]


def test_price_lookup_resolves_quesadilla_alias() -> None:
    sess = api_create_session(
        _request("req-price-quesadilla-alias-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-price-quesadilla-alias-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="how much is the quesadilla",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["intent"] == "price_lookup"
    assert "9.00" in response["agent_text"]


def test_pronoun_followup_after_price_lookup_adds_last_item() -> None:
    sess = api_create_session(
        _request("req-pronoun-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-pronoun-price"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="how much is a quesadilla?",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-pronoun-followup"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="I'll take one of those",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["items"][0]["item_id"] == "veggie_quesadilla"
    assert "would you like anything else" in response["agent_text"].lower()


def test_numeric_pronoun_followup_after_price_lookup_adds_last_item() -> None:
    sess = api_create_session(
        _request("req-numeric-pronoun-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-numeric-pronoun-price"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="how much is a quesadilla?",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-numeric-pronoun-followup"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="I'll take 1 of those.",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["items"][0]["item_id"] == "veggie_quesadilla"
    assert response["order"]["items"][0]["quantity"] == 1
    assert "would you like anything else" in response["agent_text"].lower()


def test_thats_it_asks_for_name_then_reads_back_then_confirms() -> None:
    sess = api_create_session(
        _request("req-finish-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-finish-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add two chicken tacos with no onions",
            channel="browser",
            metadata={},
        ),
    )

    done_before_name = api_turn(
        _request("req-finish-done1"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="That's it",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert (
        "what name should i put the order under"
        in done_before_name["agent_text"].lower()
    )
    assert done_before_name["order"]["customer_name"] is None

    named = api_turn(
        _request("req-finish-name"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Put the order under Fernando",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert named["order"]["customer_name"] == "Fernando"

    done_after_name = api_turn(
        _request("req-finish-done2"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="That's it",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert (
        "would you like me to confirm this order"
        in done_after_name["agent_text"].lower()
    )
    assert done_after_name["order"]["readback_performed"] is True

    first_confirm = api_turn(
        _request("req-finish-confirm1"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Yes, confirm",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert first_confirm["order"]["status"] == "confirmed"
    assert first_confirm["order"]["confirmation_id"]


def test_no_does_not_confirm_empty_order() -> None:
    sess = api_create_session(
        _request("req-no-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-no-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="no",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["status"] == "active"
    assert "what would you like to order" in response["agent_text"].lower()


def test_no_thats_all_triggers_wrap_up() -> None:
    sess = api_create_session(
        _request("req-no-thats-all-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-no-thats-all-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-no-thats-all-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="no that's all",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert "what name should i put the order under" in response["agent_text"].lower()


def test_okay_thats_all_triggers_wrap_up() -> None:
    sess = api_create_session(
        _request("req-okay-thats-all-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-okay-thats-all-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-okay-thats-all-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="okay that's all",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert "what name should i put the order under" in response["agent_text"].lower()


def test_im_ready_to_proceed_triggers_wrap_up() -> None:
    sess = api_create_session(
        _request("req-ready-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-ready-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-ready-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="I'm ready to proceed",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert "what name should i put the order under" in response["agent_text"].lower()


def test_im_done_ordering_triggers_wrap_up() -> None:
    sess = api_create_session(
        _request("req-im-done-ordering-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-im-done-ordering-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-im-done-ordering-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="I'm done ordering",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert "what name should i put the order under" in response["agent_text"].lower()


def test_no_im_done_triggers_wrap_up() -> None:
    sess = api_create_session(
        _request("req-no-im-done-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-no-im-done-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-no-im-done-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="no im done",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert "what name should i put the order under" in response["agent_text"].lower()


def test_complete_order_triggers_wrap_up() -> None:
    sess = api_create_session(
        _request("req-complete-order-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-complete-order-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-complete-order-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="complete order",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert "what name should i put the order under" in response["agent_text"].lower()


def test_finish_order_after_name_reads_back_and_asks_confirmation() -> None:
    sess = api_create_session(
        _request("req-finish-order-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-finish-order-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )
    api_turn(
        _request("req-finish-order-name"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="It's Fernando",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-finish-order-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="finish order",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["readback_performed"] is True
    assert "would you like me to confirm this order" in response["agent_text"].lower()


def test_okay_thats_all_after_name_reads_back_and_asks_confirmation() -> None:
    sess = api_create_session(
        _request("req-okay-after-name-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-okay-after-name-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )
    api_turn(
        _request("req-okay-after-name-name"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="It's Fernando",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-okay-after-name-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="okay that's all",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["readback_performed"] is True
    assert "would you like me to confirm this order" in response["agent_text"].lower()


def test_im_done_ordering_after_name_reads_back_and_asks_confirmation() -> None:
    sess = api_create_session(
        _request("req-done-ordering-after-name-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-done-ordering-after-name-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )
    api_turn(
        _request("req-done-ordering-after-name-name"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="It's Fernando",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-done-ordering-after-name-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="I'm done ordering",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["readback_performed"] is True
    assert "would you like me to confirm this order" in response["agent_text"].lower()


def test_checkout_after_name_reads_back_and_asks_confirmation() -> None:
    sess = api_create_session(
        _request("req-checkout-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-checkout-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )
    api_turn(
        _request("req-checkout-name"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="It's Fernando",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-checkout-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="checkout",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["readback_performed"] is True
    assert "would you like me to confirm this order" in response["agent_text"].lower()


def test_confirm_order_explains_missing_requirement() -> None:
    sess = api_create_session(
        _request("req-confirm-missing-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-confirm-missing-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-confirm-missing-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="confirm order",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert "what name should i put the order under" in response["agent_text"].lower()
    assert "which item" not in response["agent_text"].lower()


def test_confirm_order_succeeds_after_name_and_readback() -> None:
    sess = api_create_session(
        _request("req-confirm-ready-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-confirm-ready-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )
    api_turn(
        _request("req-confirm-ready-name"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Put the order under Fernando",
            channel="browser",
            metadata={},
        ),
    )
    confirm_before_readback = api_turn(
        _request("req-confirm-before-readback"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="confirm order",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert (
        "would you like me to confirm this order"
        in confirm_before_readback["agent_text"].lower()
    )

    api_turn(
        _request("req-confirm-ready-readback"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="that's all",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-confirm-ready-confirm"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="confirm order",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["status"] == "confirmed"
    assert response["order"]["confirmation_id"] is not None


def test_bare_name_reply_after_prompt_sets_customer_name() -> None:
    sess = api_create_session(
        _request("req-bare-name-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-bare-name-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )
    api_turn(
        _request("req-bare-name-prompt"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="that's all",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-bare-name-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Fernando",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["customer_name"] == "Fernando"


def test_bare_name_after_confirm_prompt_continues_checkout_flow() -> None:
    sess = api_create_session(
        _request("req-name-continue-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-name-continue-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one chicken taco",
            channel="browser",
            metadata={},
        ),
    )

    prompt_response = api_turn(
        _request("req-name-continue-confirm"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="confirm order",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert (
        "what name should i put the order under"
        in prompt_response["agent_text"].lower()
    )

    response = api_turn(
        _request("req-name-continue-name"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Fernando",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["customer_name"] == "Fernando"
    assert response["order"]["readback_performed"] is True
    assert "would you like me to confirm this order" in response["agent_text"].lower()


def test_remove_quesadilla_by_name_when_unambiguous() -> None:
    sess = api_create_session(
        _request("req-remove-quesadilla-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-remove-quesadilla-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one veggie quesadilla",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-remove-quesadilla-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="remove the quesadilla",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert len(response["order"]["items"]) == 0
    assert any(
        tool_call["tool_name"] == "remove_order_item"
        for tool_call in response["tool_calls"]
    )


def test_take_the_burger_off_removes_burger() -> None:
    sess = api_create_session(
        _request("req-remove-burger-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-remove-burger-add"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one classic burger",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-remove-burger-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="take the burger off",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert len(response["order"]["items"]) == 0
    assert any(
        tool_call["tool_name"] == "remove_order_item"
        for tool_call in response["tool_calls"]
    )


def test_remove_item_not_in_cart_reports_clearly() -> None:
    sess = api_create_session(
        _request("req-remove-missing-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-remove-missing-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="remove the quesadilla",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert "not currently in your order" in response["agent_text"].lower()


def test_remove_item_asks_clarification_when_multiple_matches() -> None:
    sess = api_create_session(
        _request("req-remove-ambiguous-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-remove-ambiguous-add1"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one veggie quesadilla",
            channel="browser",
            metadata={},
        ),
    )
    api_turn(
        _request("req-remove-ambiguous-add2"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Add one veggie quesadilla with no onions",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-remove-ambiguous-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="remove the quesadilla",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert len(response["order"]["items"]) == 2
    assert "more than one matching item" in response["agent_text"].lower()


def test_put_it_under_the_name_fernando_extracts_correct_name() -> None:
    sess = api_create_session(
        _request("req-name-extract-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    response = api_turn(
        _request("req-name-extract-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="Put it under the name Fernando",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["customer_name"] == "Fernando"


def test_item_only_followup_after_meat_options_adds_burrito() -> None:
    sess = api_create_session(
        _request("req-item-followup-session"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    session_id = sess["session_id"]

    api_turn(
        _request("req-item-followup-list"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="what meat options do you have",
            channel="browser",
            metadata={},
        ),
    )

    response = api_turn(
        _request("req-item-followup-turn"),
        AgentTurnRequest(
            session_id=session_id,
            utterance="The Carnitas Burritos",
            channel="browser",
            metadata={},
        ),
    ).model_dump()
    assert response["order"]["items"][0]["item_id"] == "carnitas_burrito"


def test_missing_session_returns_404() -> None:
    with pytest.raises(Exception) as exc_info:
        api_turn(
            _request("req-missing-session"),
            AgentTurnRequest(
                session_id="invalid_session",
                utterance="Hello",
                channel="browser",
                metadata={},
            ),
        )
    assert "Session not found" in str(exc_info.value)
