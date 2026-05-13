import pytest
from restaurant_agent.schemas import AgentTurnRequest, Channel
from restaurant_agent.agent import start_session, process_turn


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.mark.user_story("US-04")
def test_us_04_add_item_with_modification():
    session = start_session()

    req = AgentTurnRequest(
        session_id=session.session_id,
        utterance="Add two chicken tacos with no onions",
        channel=Channel.browser,
    )
    res = process_turn(req)

    assert res.intent == "add_order_item"
    assert any(tc.tool_name == "add_order_item" for tc in res.tool_calls)
    assert len(res.order.items) == 1
    item = res.order.items[0]
    assert item.item_id == "chicken_tacos"
    assert item.quantity == 2
    assert "no onions" in item.special_instructions
    assert "would you like anything else" in res.agent_text.lower()


@pytest.mark.user_story("US-04")
def test_us_04_broad_add_decline_does_not_mutate_order():
    session = start_session()

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="what kind of vegetarian items do you have",
            channel=Channel.browser,
        )
    )

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="give me all of it",
            channel=Channel.browser,
        )
    )

    decline = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="no",
            channel=Channel.browser,
        )
    )

    assert len(decline.order.items) == 0
    assert "won't add those items" in decline.agent_text.lower()


@pytest.mark.user_story("US-04")
def test_us_04_multi_item_add_with_aliases():
    session = start_session()

    res = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Give me a Burrito and a Burger",
            channel=Channel.browser,
        )
    )

    item_ids = [item.item_id for item in res.order.items]
    assert "carnitas_burrito" in item_ids
    assert "classic_burger" in item_ids


@pytest.mark.user_story("US-04")
def test_us_04_multi_item_add_fish_tacos_and_burger():
    session = start_session()

    res = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="the fish tacos and a burger",
            channel=Channel.browser,
        )
    )

    item_ids = [item.item_id for item in res.order.items]
    assert item_ids == ["crispy_fish_tacos", "classic_burger"]
    assert "would you like anything else" in res.agent_text.lower()


@pytest.mark.user_story("US-04")
def test_us_04_unsupported_modification_confirmation_yes_adds_special_instruction():
    session = start_session()

    first = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add one chicken taco with extra queso",
            channel=Channel.browser,
        )
    )
    assert len(first.order.items) == 0
    assert "special instruction" in first.agent_text.lower()

    second = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="yes",
            channel=Channel.browser,
        )
    )
    assert len(second.order.items) == 1
    item = second.order.items[0]
    assert item.item_id == "chicken_tacos"
    assert item.special_instructions == ["extra queso"]
    assert item.known_modifications == []
    assert second.order.subtotal == 8.50
    assert second.order.total == 9.20
    assert any(tc.tool_name == "add_order_item" for tc in second.tool_calls)
