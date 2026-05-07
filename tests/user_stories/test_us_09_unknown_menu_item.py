import pytest
from restaurant_agent.schemas import AgentTurnRequest, Channel
from restaurant_agent.agent import start_session, process_turn


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.mark.user_story("US-09")
def test_us_09_unknown_menu_item():
    session = start_session()

    req = AgentTurnRequest(
        session_id=session.session_id,
        utterance="Add one lobster pizza",
        channel=Channel.browser,
    )
    res = process_turn(req)

    # Degraded parser should refuse since it's not a known item
    assert len(res.order.items) == 0
    assert not any(tc.status == "success" for tc in res.tool_calls)
    assert res.agent_text is not None
