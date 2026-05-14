import pytest
from starlette.requests import Request
from urllib.parse import urlencode
from xml.etree import ElementTree

from tests.assertions import assert_offer_more_items
from restaurant_agent.api import (
    api_debug_session,
    voice_config_check,
    voice_incoming,
    voice_status,
    voice_turn,
)
from restaurant_agent.order_store import clear_orders, get_order
from restaurant_agent.session_store import (
    clear_sessions,
    find_session_by_twilio_call_sid,
)


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    clear_sessions()
    clear_orders()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ENABLE_TWILIO", "true")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-test-account")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "super-secret-token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+15551234567")
    monkeypatch.setenv("TWILIO_WEBHOOK_BASE_URL", "https://example.com")
    monkeypatch.setenv("MENU_INDEX_PATH", str(tmp_path))


def _parse_twiml(response_text: str) -> ElementTree.Element:
    return ElementTree.fromstring(response_text)


def _build_form_request(
    path: str,
    form_data: dict[str, str],
    request_id: str = "req-test",
) -> Request:
    body = urlencode(form_data).encode("utf-8")
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", str(len(body)).encode("utf-8")),
        ],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    sent = False

    async def receive() -> dict[str, object]:
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(scope, receive)
    request.state.request_id = request_id
    return request


def _build_get_request(path: str, request_id: str = "req-debug") -> Request:
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive=None,
    )
    request.state.request_id = request_id
    return request


def test_voice_config_check_returns_safe_status() -> None:
    data = voice_config_check()

    assert data["enabled"] is True
    assert data["configured"] is True
    assert data["phone_number_configured"] is True
    assert data["webhook_base_url_configured"] is True
    assert data["missing_fields"] == []
    assert "super-secret-token" not in str(data)
    assert "AC-test-account" not in str(data)


@pytest.mark.asyncio
async def test_voice_incoming_returns_twiml_and_creates_twilio_session() -> None:
    response = await voice_incoming(
        _build_form_request("/voice/incoming", {"CallSid": "CA123"})
    )

    assert response.status_code == 200
    response_text = response.body.decode("utf-8")
    assert "super-secret-token" not in response_text

    root = _parse_twiml(response_text)
    assert root.tag == "Response"
    gather = root.find("Gather")
    assert gather is not None
    assert gather.attrib["input"] == "speech"
    assert gather.attrib["action"] == "https://example.com/voice/turn"
    assert gather.attrib["speechTimeout"] == "auto"
    assert gather.attrib["timeout"] == "4"
    assert "Welcome" in "".join(root.itertext())

    session = find_session_by_twilio_call_sid("CA123")
    assert session is not None
    assert session.channel.value == "twilio"
    assert session.twilio_call_sid == "CA123"


@pytest.mark.asyncio
async def test_voice_turn_returns_twiml_with_menu_response() -> None:
    await voice_incoming(_build_form_request("/voice/incoming", {"CallSid": "CA456"}))

    response = await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA456", "SpeechResult": "What tacos do you have?"},
        )
    )

    assert response.status_code == 200
    response_text = response.body.decode("utf-8")
    root = _parse_twiml(response_text)
    assert root.tag == "Response"
    gather = root.find("Gather")
    assert gather is not None
    assert gather.attrib["input"] == "speech"
    assert gather.attrib["action"] == "https://example.com/voice/turn"
    assert gather.attrib["speechTimeout"] == "auto"
    assert gather.attrib["timeout"] == "4"

    response_text = " ".join(root.itertext()).lower()
    assert "taco" in response_text
    assert "super-secret-token" not in response.body.decode("utf-8")


@pytest.mark.asyncio
async def test_voice_turn_creates_session_for_unknown_call_sid() -> None:
    response = await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA999", "SpeechResult": "What tacos do you have?"},
        )
    )

    assert response.status_code == 200
    root = _parse_twiml(response.body.decode("utf-8"))
    assert root.find("Gather") is not None

    session = find_session_by_twilio_call_sid("CA999")
    assert session is not None
    assert session.channel.value == "twilio"


@pytest.mark.asyncio
async def test_voice_turn_bare_name_capture_continues_checkout_flow() -> None:
    await voice_incoming(_build_form_request("/voice/incoming", {"CallSid": "CA555"}))

    await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA555", "SpeechResult": "Add one chicken taco"},
        )
    )

    name_prompt = await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA555", "SpeechResult": "confirm order"},
        )
    )
    assert (
        "what name should i put the order under"
        in " ".join(_parse_twiml(name_prompt.body.decode("utf-8")).itertext()).lower()
    )

    name_response = await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA555", "SpeechResult": "Fernando."},
        )
    )
    name_text = " ".join(
        _parse_twiml(name_response.body.decode("utf-8")).itertext()
    ).lower()
    assert "got it, the order is under fernando" in name_text
    assert "would you like me to confirm this order" in name_text

    session = find_session_by_twilio_call_sid("CA555")
    assert session is not None
    order = get_order(session.session_id)
    assert order is not None
    assert order.customer_name == "Fernando"
    assert order.readback_performed is True


@pytest.mark.asyncio
async def test_voice_turn_adds_fish_tacos_and_burger() -> None:
    await voice_incoming(_build_form_request("/voice/incoming", {"CallSid": "CA556"}))

    response = await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA556", "SpeechResult": "the fish tacos and a burger"},
        )
    )

    response_text = " ".join(
        _parse_twiml(response.body.decode("utf-8")).itertext()
    ).lower()
    assert_offer_more_items(response_text)

    session = find_session_by_twilio_call_sid("CA556")
    assert session is not None
    order = get_order(session.session_id)
    assert order is not None
    item_ids = [item.item_id for item in order.items]
    assert item_ids == ["crispy_fish_tacos", "classic_burger"]


@pytest.mark.asyncio
async def test_voice_turn_pronoun_followup_adds_last_mentioned_item() -> None:
    await voice_incoming(_build_form_request("/voice/incoming", {"CallSid": "CA559"}))

    first_response = await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA559", "SpeechResult": "How much is a quesadilla?"},
        )
    )
    first_text = " ".join(
        _parse_twiml(first_response.body.decode("utf-8")).itertext()
    ).lower()
    assert "9.00" in first_text

    session = find_session_by_twilio_call_sid("CA559")
    assert session is not None
    first_session_id = session.session_id
    assert session.last_mentioned_item_id == "veggie_quesadilla"

    second_response = await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA559", "SpeechResult": "I'll take one of those."},
        )
    )
    second_text = " ".join(
        _parse_twiml(second_response.body.decode("utf-8")).itertext()
    ).lower()
    assert_offer_more_items(second_text)

    session_after = find_session_by_twilio_call_sid("CA559")
    assert session_after is not None
    assert session_after.session_id == first_session_id
    assert session_after.last_mentioned_item_id == "veggie_quesadilla"

    order = get_order(session_after.session_id)
    assert order is not None
    item_ids = [item.item_id for item in order.items]
    assert item_ids == ["veggie_quesadilla"]


@pytest.mark.asyncio
async def test_voice_turn_numeric_pronoun_followup_real_transcript_regression() -> None:
    await voice_incoming(_build_form_request("/voice/incoming", {"CallSid": "CA559N"}))

    first_response = await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA559N", "SpeechResult": "How much is a quesadilla?"},
        )
    )
    first_text = " ".join(
        _parse_twiml(first_response.body.decode("utf-8")).itertext()
    ).lower()
    assert "9.00" in first_text

    session = find_session_by_twilio_call_sid("CA559N")
    assert session is not None
    first_session_id = session.session_id
    assert session.last_mentioned_item_id == "veggie_quesadilla"

    second_response = await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA559N", "SpeechResult": "I'll take 1 of those."},
        )
    )
    second_text = " ".join(
        _parse_twiml(second_response.body.decode("utf-8")).itertext()
    ).lower()
    assert_offer_more_items(second_text)
    assert "i'm not sure which item" not in second_text

    session_after = find_session_by_twilio_call_sid("CA559N")
    assert session_after is not None
    assert session_after.session_id == first_session_id
    order = get_order(session_after.session_id)
    assert order is not None
    assert [item.item_id for item in order.items] == ["veggie_quesadilla"]
    assert order.items[0].quantity == 1

    debug = api_debug_session(
        _build_get_request(f"/api/debug/session/{session_after.session_id}"),
        session_after.session_id,
    ).model_dump()
    diagnostics = debug["recent_turn_diagnostics"]
    assert diagnostics[-1]["raw_transcript"] == "I'll take 1 of those."
    assert diagnostics[-1]["normalized_transcript"] == "i'll take 1 of those"
    assert diagnostics[-1]["selected_tool_name"] == "add_order_item"


@pytest.mark.asyncio
async def test_voice_turn_pronoun_variants_and_debug_diagnostics() -> None:
    await voice_incoming(_build_form_request("/voice/incoming", {"CallSid": "CA561"}))

    await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA561", "SpeechResult": "How much is a quesadilla?"},
        )
    )

    for utterance in [
        "I will take one of those",
        "I'll take one of those please",
        "One of those",
        "I'll take it",
    ]:
        call_sid = f"CA561-{utterance.replace(' ', '-')}"
        await voice_incoming(
            _build_form_request("/voice/incoming", {"CallSid": call_sid})
        )
        await voice_turn(
            _build_form_request(
                "/voice/turn",
                {"CallSid": call_sid, "SpeechResult": "How much is a quesadilla?"},
            )
        )
        await voice_turn(
            _build_form_request(
                "/voice/turn",
                {"CallSid": call_sid, "SpeechResult": utterance},
            )
        )
        session = find_session_by_twilio_call_sid(call_sid)
        assert session is not None
        order = get_order(session.session_id)
        assert order is not None
        assert [item.item_id for item in order.items] == ["veggie_quesadilla"]

    session = find_session_by_twilio_call_sid("CA561")
    assert session is not None
    debug = api_debug_session(
        _build_get_request(f"/api/debug/session/{session.session_id}"),
        session.session_id,
    ).model_dump()
    diagnostics = debug["recent_turn_diagnostics"]
    assert diagnostics
    assert diagnostics[-1]["raw_transcript"] == "How much is a quesadilla?"
    assert diagnostics[-1]["normalized_transcript"]
    assert diagnostics[-1]["twilio_call_sid"] == "CA561"
    assert "TWILIO_AUTH_TOKEN" not in str(debug)
    assert "ANTHROPIC_API_KEY" not in str(debug)


@pytest.mark.asyncio
async def test_voice_turn_ill_take_fish_tacos_and_burger_works_first_try() -> None:
    await voice_incoming(_build_form_request("/voice/incoming", {"CallSid": "CA560"}))

    response = await voice_turn(
        _build_form_request(
            "/voice/turn",
            {
                "CallSid": "CA560",
                "SpeechResult": "Ill take the fish tacos and a burger.",
            },
        )
    )

    response_text = " ".join(
        _parse_twiml(response.body.decode("utf-8")).itertext()
    ).lower()
    assert_offer_more_items(response_text)

    session = find_session_by_twilio_call_sid("CA560")
    assert session is not None
    order = get_order(session.session_id)
    assert order is not None
    item_ids = [item.item_id for item in order.items]
    assert item_ids == ["crispy_fish_tacos", "classic_burger"]


@pytest.mark.asyncio
async def test_voice_turn_remove_by_item_name_and_persist_context() -> None:
    await voice_incoming(_build_form_request("/voice/incoming", {"CallSid": "CA562"}))

    await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA562", "SpeechResult": "How much is a quesadilla?"},
        )
    )
    await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA562", "SpeechResult": "I'll take one of those."},
        )
    )

    session = find_session_by_twilio_call_sid("CA562")
    assert session is not None
    first_session_id = session.session_id
    assert session.last_mentioned_item_id == "veggie_quesadilla"

    response = await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA562", "SpeechResult": "remove the quesadilla"},
        )
    )
    response_text = " ".join(
        _parse_twiml(response.body.decode("utf-8")).itertext()
    ).lower()
    assert "removed" in response_text

    session_after = find_session_by_twilio_call_sid("CA562")
    assert session_after is not None
    assert session_after.session_id == first_session_id
    order = get_order(session_after.session_id)
    assert order is not None
    assert len(order.items) == 0


@pytest.mark.asyncio
async def test_voice_turn_returns_goodbye_after_confirmation() -> None:
    await voice_incoming(_build_form_request("/voice/incoming", {"CallSid": "CA557"}))

    await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA557", "SpeechResult": "Add one chicken taco"},
        )
    )
    await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA557", "SpeechResult": "confirm order"},
        )
    )
    await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA557", "SpeechResult": "Fernando"},
        )
    )

    response = await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA557", "SpeechResult": "yes confirm"},
        )
    )

    root = _parse_twiml(response.body.decode("utf-8"))
    assert root.find("Hangup") is not None
    assert root.find("Gather") is None


@pytest.mark.asyncio
async def test_voice_turn_returns_goodbye_after_cancellation() -> None:
    await voice_incoming(_build_form_request("/voice/incoming", {"CallSid": "CA558"}))

    await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA558", "SpeechResult": "Add one chicken taco"},
        )
    )

    response = await voice_turn(
        _build_form_request(
            "/voice/turn",
            {"CallSid": "CA558", "SpeechResult": "cancel my order"},
        )
    )

    root = _parse_twiml(response.body.decode("utf-8"))
    assert root.find("Hangup") is not None
    assert root.find("Gather") is None


@pytest.mark.asyncio
async def test_voice_status_acknowledges_callback() -> None:
    response = await voice_status(
        _build_form_request(
            "/voice/status",
            {"CallSid": "CA777", "CallStatus": "completed"},
        )
    )

    assert response["status"] == "acknowledged"
    assert response["call_sid"] == "CA777"
    assert response["call_status"] == "completed"
