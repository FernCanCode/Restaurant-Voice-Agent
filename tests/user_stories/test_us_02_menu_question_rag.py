import pytest
from restaurant_agent.schemas import AgentTurnRequest, Channel
from restaurant_agent.agent import start_session, process_turn


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.mark.user_story("US-02")
def test_us_02_menu_question_rag():
    session = start_session()

    req = AgentTurnRequest(
        session_id=session.session_id,
        utterance="What tacos do you have?",
        channel=Channel.browser,
    )
    res = process_turn(req)

    assert res.intent == "search_menu"
    assert any(tc.tool_name == "search_menu" for tc in res.tool_calls)
    assert len(res.order.items) == 0
