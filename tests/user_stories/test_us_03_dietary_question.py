import pytest
from restaurant_agent.schemas import AgentTurnRequest, Channel
from restaurant_agent.agent import start_session, process_turn


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.mark.user_story("US-03")
def test_us_03_dietary_question():
    session = start_session()

    req = AgentTurnRequest(
        session_id=session.session_id,
        utterance="Is the black bean bowl safe for a peanut allergy?",
        channel=Channel.browser,
    )
    res = process_turn(req)

    # Degraded parser should refuse allergy guarantee or route to check_dietary
    assert len(res.order.items) == 0
    # The degraded parser actually routes this to check_dietary_info with safe_to_execute=True
    # Let's verify that
    if res.tool_calls:
        assert res.tool_calls[0].tool_name == "check_dietary_info"
    else:
        assert (
            "allergy" in res.agent_text.lower() or "guarantee" in res.agent_text.lower()
        )


@pytest.mark.user_story("US-03")
def test_us_03_vegetarian_broad_add_requires_confirmation():
    session = start_session()

    list_response = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="what kind of vegetarian items do you have",
            channel=Channel.browser,
        )
    )
    assert list_response.intent == "search_menu"
    assert "vegetarian" in list_response.agent_text.lower()

    broad_add_response = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="give me all of that",
            channel=Channel.browser,
        )
    )
    assert len(broad_add_response.order.items) == 0
    assert "just to confirm" in broad_add_response.agent_text.lower()
    assert "black bean bowl" in broad_add_response.agent_text.lower()
    assert "veggie quesadilla" in broad_add_response.agent_text.lower()

    confirmed_response = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="yes",
            channel=Channel.browser,
        )
    )
    item_ids = {item.item_id for item in confirmed_response.order.items}
    assert "black_bean_bowl" in item_ids
    assert "veggie_quesadilla" in item_ids
    assert "would you like anything else" in confirmed_response.agent_text.lower()


@pytest.mark.user_story("US-03")
def test_us_03_vegetarian_broad_add_those_variant_requires_confirmation():
    session = start_session()

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="what kind of vegetarian items do you have",
            channel=Channel.browser,
        )
    )

    broad_add_response = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="give me all of those",
            channel=Channel.browser,
        )
    )
    assert len(broad_add_response.order.items) == 0
    assert "just to confirm" in broad_add_response.agent_text.lower()
