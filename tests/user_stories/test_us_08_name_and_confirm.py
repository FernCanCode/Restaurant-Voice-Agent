import pytest
from tests.assertions import assert_offer_more_items
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
    assert_offer_more_items(res_add.agent_text)

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
            utterance="confirm order",
            channel=Channel.browser,
        )
    )
    assert res_conf.order.status.value == "confirmed"
    assert res_conf.order.confirmation_id is not None


@pytest.mark.user_story("US-08")
def test_us_08_no_thats_all_and_confirm_requirements():
    session = start_session()

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add one chicken taco",
            channel=Channel.browser,
        )
    )

    res_done = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="no that's all",
            channel=Channel.browser,
        )
    )
    assert "what name should i put the order under" in res_done.agent_text.lower()

    res_confirm = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="confirm order",
            channel=Channel.browser,
        )
    )
    assert "what name should i put the order under" in res_confirm.agent_text.lower()


@pytest.mark.user_story("US-08")
def test_us_08_bare_name_and_its_name_capture():
    session = start_session()

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add one chicken taco",
            channel=Channel.browser,
        )
    )
    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="I'm ready",
            channel=Channel.browser,
        )
    )

    res_name = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Fernando",
            channel=Channel.browser,
        )
    )
    assert res_name.order.customer_name == "Fernando"
    assert res_name.order.readback_performed is True
    assert "would you like me to confirm this order" in res_name.agent_text.lower()

    session2 = start_session()
    res_explicit = process_turn(
        AgentTurnRequest(
            session_id=session2.session_id,
            utterance="It's Fernando",
            channel=Channel.browser,
        )
    )
    assert res_explicit.order.customer_name == "Fernando"


@pytest.mark.user_story("US-08")
def test_us_08_finish_order_after_name_reads_back():
    session = start_session()

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add one chicken taco",
            channel=Channel.browser,
        )
    )
    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="It's Fernando",
            channel=Channel.browser,
        )
    )

    res = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="finish order",
            channel=Channel.browser,
        )
    )
    assert res.order.readback_performed is True
    assert "would you like me to confirm this order" in res.agent_text.lower()


@pytest.mark.user_story("US-08")
def test_us_08_okay_thats_all_and_done_ordering_follow_checkout_flow():
    session = start_session()

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add one chicken taco",
            channel=Channel.browser,
        )
    )

    res_done_before_name = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="okay that's all",
            channel=Channel.browser,
        )
    )
    assert (
        "what name should i put the order under"
        in res_done_before_name.agent_text.lower()
    )

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Fernando",
            channel=Channel.browser,
        )
    )

    res_done_after_name = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="I'm done ordering",
            channel=Channel.browser,
        )
    )
    assert res_done_after_name.order.readback_performed is True
    assert (
        "would you like me to confirm this order"
        in res_done_after_name.agent_text.lower()
    )


@pytest.mark.user_story("US-08")
def test_us_08_confirm_then_bare_name_continues_checkout_flow():
    session = start_session()

    process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Add one chicken taco",
            channel=Channel.browser,
        )
    )

    res_confirm = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="confirm order",
            channel=Channel.browser,
        )
    )
    assert "what name should i put the order under" in res_confirm.agent_text.lower()

    res_name = process_turn(
        AgentTurnRequest(
            session_id=session.session_id,
            utterance="Fernando",
            channel=Channel.browser,
        )
    )
    assert res_name.order.customer_name == "Fernando"
    assert res_name.order.readback_performed is True
    assert "would you like me to confirm this order" in res_name.agent_text.lower()
