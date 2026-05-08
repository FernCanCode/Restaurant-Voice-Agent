import pytest
from starlette.requests import Request
from urllib.parse import urlencode
from xml.etree import ElementTree

from restaurant_agent.api import (
    voice_config_check,
    voice_incoming,
    voice_status,
    voice_turn,
)
from restaurant_agent.order_store import clear_orders
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
    assert root.find("Gather") is not None

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
