import pytest
from starlette.requests import Request

from restaurant_agent.api import (
    api_cancel,
    api_confirm,
    api_create_session,
    api_debug_session,
    api_get_order,
    api_get_session,
    api_readback,
    api_recent_sessions,
)
from restaurant_agent.order_store import add_item, clear_orders, set_customer_name
from restaurant_agent.schemas import CreateSessionRequest, MenuItem
from restaurant_agent.session_store import clear_sessions


def _request(path: str, request_id: str) -> Request:
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
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


@pytest.fixture(autouse=True)
def setup_teardown():
    clear_sessions()
    clear_orders()
    yield
    clear_sessions()
    clear_orders()


@pytest.fixture
def dummy_menu_item():
    return MenuItem(
        id="test_item",
        name="Test Item",
        category="Test",
        description="",
        base_price=10.0,
        available=True,
        source_text="",
        source_type="html",
    )


def test_sessions_flow(dummy_menu_item) -> None:
    data = api_create_session(
        _request("/api/sessions", "req-sess-1"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    sess_id = data["session_id"]
    assert sess_id.startswith("sess_")

    session = api_get_session(sess_id)
    assert session["session_id"] == sess_id

    order = api_get_order(sess_id)
    assert order["session_id"] == sess_id

    with pytest.raises(Exception) as exc_info:
        api_get_session("invalid_id")
    assert "404" in repr(exc_info.value) or "Session not found" in str(exc_info.value)

    add_item(sess_id, dummy_menu_item)

    with pytest.raises(Exception) as exc_info:
        api_confirm(sess_id)
    assert "customer name" in str(exc_info.value)

    set_customer_name(sess_id, "Alice")

    readback = api_readback(sess_id)
    assert readback["status"] == "success"

    confirmed = api_confirm(sess_id)
    assert confirmed["status"] == "success"
    assert confirmed["order"]["status"] == "confirmed"

    data2 = api_create_session(
        _request("/api/sessions", "req-sess-2"),
        CreateSessionRequest(channel="browser"),
    ).model_dump()
    sess_id_2 = data2["session_id"]
    cancelled = api_cancel(sess_id_2)
    assert cancelled["status"] == "success"
    assert cancelled["order"]["status"] == "cancelled"

    recent = api_recent_sessions(_request("/api/debug/sessions/recent", "req-recent"))
    assert len(recent.model_dump()["sessions"]) == 2

    debug_data = api_debug_session(
        _request(f"/api/debug/session/{sess_id}", "req-debug"),
        sess_id,
    ).model_dump()
    assert debug_data["session_id"] == sess_id
    assert debug_data["order_status"] == "confirmed"
    assert debug_data["customer_name"] == "Alice"
