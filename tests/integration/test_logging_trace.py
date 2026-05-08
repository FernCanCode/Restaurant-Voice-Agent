import pytest
from starlette.requests import Request
from urllib.parse import urlencode

from restaurant_agent.api import app
from restaurant_agent.middleware import RequestIDMiddleware
from restaurant_agent.order_store import clear_orders
from restaurant_agent.session_store import clear_sessions


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_sessions()
    clear_orders()
    monkeypatch.setenv("ENABLE_TWILIO", "true")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-test-account")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "super-secret-token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+15551234567")
    monkeypatch.setenv("TWILIO_WEBHOOK_BASE_URL", "https://example.com")


def _build_form_request(
    path: str,
    form_data: dict[str, str],
    request_id: str | None = None,
) -> Request:
    body = urlencode(form_data).encode("utf-8")
    headers = [
        (b"content-type", b"application/x-www-form-urlencoded"),
        (b"content-length", str(len(body)).encode("utf-8")),
    ]
    if request_id is not None:
        headers.append((b"x-request-id", request_id.encode("utf-8")))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers,
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

    return Request(scope, receive)


async def _dispatch_voice_incoming(request: Request):
    middleware = RequestIDMiddleware(app)
    messages = []

    async def send(message):
        messages.append(message)

    await middleware(request.scope, request.receive, send)

    start = next(
        message for message in messages if message["type"] == "http.response.start"
    )
    headers = {
        key.decode("latin-1"): value.decode("latin-1")
        for key, value in start["headers"]
    }

    class ResponseStub:
        def __init__(self, headers):
            self.headers = headers

    return ResponseStub(headers)


@pytest.mark.asyncio
async def test_twilio_incoming_response_includes_request_id() -> None:
    response = await _dispatch_voice_incoming(
        _build_form_request("/voice/incoming", {"CallSid": "CA100"})
    )
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


@pytest.mark.asyncio
async def test_twilio_incoming_preserves_request_id() -> None:
    test_id = "twilio-req-456"
    response = await _dispatch_voice_incoming(
        _build_form_request(
            "/voice/incoming",
            {"CallSid": "CA101"},
            request_id=test_id,
        )
    )
    assert response.headers.get("x-request-id") == test_id
