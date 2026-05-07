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
