import pytest
from restaurant_agent.schemas import AgentTurnRequest, Channel
from restaurant_agent.agent import start_session, process_turn


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.mark.user_story("US-10")
def test_us_10_ambiguous_removal():
    session = start_session()

    # Add an item
    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add one chicken taco",
            channel=Channel.browser,
        )
    )

    # Send an ambiguous removal (no line item id provided in context, though in the actual system the fallback parser checks if line_item_id is present)
    req = AgentTurnRequest(
        session_id=session.session_id,
        utterance="Remove the chicken taco",
        channel=Channel.browser,
        metadata={"line_item_id": None},
    )
    res = process_turn(req)

    # Since line_item_id is missing/ambiguous, it should refuse or ask for clarification
    assert len(res.order.items) == 1
    assert "clarification" in res.intent or "remove" in res.intent
    assert (
        "Which item" in res.agent_text
        or "Which order" in res.agent_text
        or "sure" in res.agent_text
    )
