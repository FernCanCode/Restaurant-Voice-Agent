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
