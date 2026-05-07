import pytest
from restaurant_agent.schemas import AgentTurnRequest, Channel
from restaurant_agent.agent import start_session, process_turn


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.mark.user_story("US-08")
def test_us_08_name_and_confirm():
    session = start_session()

    # Empty order confirmation should fail
    res_fail = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Yes, confirm",
            channel=Channel.browser,
        )
    )
    # It attempts to confirm but order is empty
    assert res_fail.intent == "confirm_order"
    assert res_fail.order.status != "confirmed"

    # Add item
    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add one chicken taco",
            channel=Channel.browser,
        )
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

    # Readback
    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Read back my order",
            channel=Channel.browser,
        )
    )

    # Confirm
    res_conf = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Yes, confirm",
            channel=Channel.browser,
        )
    )
    assert res_conf.order.status.value == "confirmed"
