import pytest
from starlette.requests import Request
from urllib.parse import urlencode

from restaurant_agent.api import api_browser_start_call, get_browser_ui, voice_incoming
from restaurant_agent.order_store import clear_orders
from restaurant_agent.session_store import (
    clear_sessions,
    find_session_by_twilio_call_sid,
)


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_sessions()
    clear_orders()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ENABLE_TWILIO", "true")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-test-account")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "super-secret-token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+15551234567")
    monkeypatch.setenv("TWILIO_WEBHOOK_BASE_URL", "https://example.com")


@pytest.mark.user_story("US-01")
def test_us_01_start_voice_call():
    # 1. GET / returns HTTP 200 and required strings
    html_res = get_browser_ui()
    assert html_res.status_code == 200
    html_text = html_res.body.decode("utf-8")
    assert "Restaurant Voice Ordering Agent" in html_text
    assert "Start Voice Order" in html_text
    assert "Speak" in html_text
    assert "Typed fallback" in html_text
    assert "Auto-listen after agent responses" in html_text
    assert "Microphone access was blocked" in html_text
    assert "Chrome or Chromium" in html_text
    assert "Embedded previews may block microphone permissions" in html_text
    assert (
        "Browser speech recognition does not expose a sensitivity control" in html_text
    )
    assert "cleanTextForSpeech" in html_text

    # 2. POST /api/browser/start-call returns greeting, empty order, etc
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/browser/start-call",
            "raw_path": b"/api/browser/start-call",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive=None,
    )
    request.state.request_id = "req-us-01-browser"
    data = api_browser_start_call(request).model_dump()
    assert "Welcome" in data["agent_text"]
    assert data["session_id"]
    assert "request_id" in data

    # 3. Order should be empty and total 0.0
    order = data["order"]
    assert len(order["items"]) == 0
    assert order["total"] == 0.0


@pytest.mark.user_story("US-01")
@pytest.mark.asyncio
async def test_us_01_start_voice_call_twilio_path():
    body = urlencode({"CallSid": "CA-US01"}).encode("utf-8")
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/voice/incoming",
        "raw_path": b"/voice/incoming",
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
    request.state.request_id = "req-us-01-twilio"
    response = await voice_incoming(request)
    assert response.status_code == 200
    response_text = response.body.decode("utf-8")
    assert "<Response>" in response_text
    assert "<Gather" in response_text
    assert "Welcome" in response_text

    session = find_session_by_twilio_call_sid("CA-US01")
    assert session is not None
    assert session.channel.value == "twilio"
