import pytest
from restaurant_agent.schemas import AgentTurnRequest, Channel
from restaurant_agent.agent import start_session, process_turn


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.mark.user_story("US-07")
def test_us_07_summary_and_total():
    session = start_session()

    price_req = AgentTurnRequest(
        session_id=session.session_id,
        utterance="how much is the veggie quesadilla",
        channel=Channel.browser,
    )
    price_res = process_turn(price_req)
    assert price_res.intent == "price_lookup"
    assert "9.00" in price_res.agent_text
    assert "unavailable" not in price_res.agent_text.lower()

    # Add an item first
    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add two chicken tacos",
            channel=Channel.browser,
        )
    )

    # Check total
    req = AgentTurnRequest(
        session_id=session.session_id,
        utterance="What is my total?",
        channel=Channel.browser,
    )
    res = process_turn(req)

    assert res.intent == "compute_total"
    assert "total" in res.agent_text.lower()
    assert "would you like anything else" in res.agent_text.lower()

    # Readback
    req2 = AgentTurnRequest(
        session_id=session.session_id,
        utterance="Read back my order",
        channel=Channel.browser,
    )
    res2 = process_turn(req2)

    assert res2.intent == "get_order_summary"
    assert res2.order.readback_performed is True
