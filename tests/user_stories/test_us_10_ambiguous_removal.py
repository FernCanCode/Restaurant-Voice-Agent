import pytest
from restaurant_agent.schemas import AgentTurnRequest, Channel
from restaurant_agent.agent import start_session, process_turn


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.mark.user_story("US-10")
def test_us_10_ambiguous_removal():
    session = start_session()

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add one chicken taco with no onions",
            channel=Channel.browser,
        )
    )
    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add one chicken taco with extra salsa",
            channel=Channel.browser,
        )
    )

    res = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Remove the chicken taco",
            channel=Channel.browser,
        )
    )

    assert len(res.order.items) == 2
    assert "more than one matching item" in res.agent_text.lower()


@pytest.mark.user_story("US-10")
def test_us_10_remove_taco_then_fish_taco_removes_not_adds():
    session = start_session()

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add chicken taco",
            channel=Channel.browser,
        )
    )
    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add fish taco",
            channel=Channel.browser,
        )
    )

    clarify = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Remove the taco",
            channel=Channel.browser,
        )
    )
    assert len(clarify.order.items) == 2
    assert "which item would you like to remove" in clarify.agent_text.lower()

    resolved = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="fish taco",
            channel=Channel.browser,
        )
    )
    assert len(resolved.order.items) == 1
    assert resolved.order.items[0].item_id == "chicken_tacos"
    assert any(tc.tool_name == "remove_order_item" for tc in resolved.tool_calls)
    assert not any(item.item_id == "crispy_fish_tacos" for item in resolved.order.items)


@pytest.mark.user_story("US-10")
def test_us_10_remove_taco_then_chicken_taco_removes_chicken():
    session = start_session()

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add chicken taco",
            channel=Channel.browser,
        )
    )
    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add fish taco",
            channel=Channel.browser,
        )
    )

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Remove the taco",
            channel=Channel.browser,
        )
    )

    resolved = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="chicken taco",
            channel=Channel.browser,
        )
    )
    assert len(resolved.order.items) == 1
    assert resolved.order.items[0].item_id == "crispy_fish_tacos"
    assert any(tc.tool_name == "remove_order_item" for tc in resolved.tool_calls)


@pytest.mark.user_story("US-10")
def test_us_10_short_item_followup_after_drinks_list():
    session = start_session()

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="what drinks do you have",
            channel=Channel.browser,
        )
    )

    res = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="The lemonade",
            channel=Channel.browser,
        )
    )
    assert len(res.order.items) == 1
    assert res.order.items[0].item_id == "lemonade"


@pytest.mark.user_story("US-10")
def test_us_10_unambiguous_remove_by_name():
    session = start_session()

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add one veggie quesadilla",
            channel=Channel.browser,
        )
    )

    res = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Remove the quesadilla",
            channel=Channel.browser,
        )
    )
    assert len(res.order.items) == 0
    assert "removed" in res.agent_text.lower()
