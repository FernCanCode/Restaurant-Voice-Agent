import pytest
from starlette.requests import Request

from restaurant_agent.api import api_create_session, api_turn
from restaurant_agent.schemas import AgentTurnRequest, CreateSessionRequest


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
