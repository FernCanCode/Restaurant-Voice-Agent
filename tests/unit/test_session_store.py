import pytest
from restaurant_agent.schemas import Channel, DialogueMode
from restaurant_agent.session_store import (
    create_session,
    append_turn,
    find_session_by_twilio_call_sid,
    list_recent_sessions,
    clear_sessions,
)


@pytest.fixture(autouse=True)
def setup_teardown():
    clear_sessions()
    yield
    clear_sessions()


def test_create_browser_session():
    state = create_session(channel=Channel.browser)
    assert state.session_id.startswith("sess_")
    assert state.channel == Channel.browser
    assert state.dialogue_mode == DialogueMode.GREETING


def test_create_twilio_session():
    state = create_session(channel=Channel.twilio, twilio_call_sid="CA12345")
    assert state.channel == Channel.twilio
    assert state.twilio_call_sid == "CA12345"


def test_find_session_by_twilio_call_sid():
    create_session(channel=Channel.twilio, twilio_call_sid="CA123")
    state = find_session_by_twilio_call_sid("CA123")
    assert state is not None
    assert state.twilio_call_sid == "CA123"


def test_append_turn():
    state = create_session()
    state = append_turn(state.session_id, "user", "hello", "req_1")
    assert len(state.turns) == 1
    assert state.turns[0].role == "user"
    assert "req_1" in state.request_ids


def test_list_recent_sessions():
    create_session()
    create_session()
    assert len(list_recent_sessions(limit=5)) == 2
