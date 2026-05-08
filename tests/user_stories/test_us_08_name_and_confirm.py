import pytest
from restaurant_agent.schemas import AgentTurnRequest, Channel
from restaurant_agent.agent import start_session, process_turn


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.mark.user_story("US-08")
def test_us_08_name_and_confirm():
    session = start_session()

    # Add item
    res_add = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add one chicken taco",
            channel=Channel.browser,
        )
    )
    assert "would you like anything else" in res_add.agent_text.lower()

    # Saying that's it before a name should ask for the name
    res_done_before_name = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="That's it",
            channel=Channel.browser,
        )
    )
    assert (
        "what name should i put the order under"
        in res_done_before_name.agent_text.lower()
    )

    # Set name
    res_name = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Put the order under Fernando",
            channel=Channel.browser,
        )
    )
    assert res_name.intent == "set_customer_name"
    assert res_name.order.customer_name == "Fernando"

    # Saying that's it after the name should read back and ask for confirmation
    res_done_after_name = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="That's it",
            channel=Channel.browser,
        )
    )
    assert res_done_after_name.order.readback_performed is True
    assert (
        "would you like me to confirm this order"
        in res_done_after_name.agent_text.lower()
    )

    # Confirm after readback
    res_conf = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Yes, confirm",
            channel=Channel.browser,
        )
    )
    assert res_conf.order.status.value == "confirmed"
    assert res_conf.order.confirmation_id is not None
