import pytest
from fastapi.testclient import TestClient

from restaurant_agent.api import app
from restaurant_agent.order_store import add_item, clear_orders, set_customer_name
from restaurant_agent.schemas import MenuItem
from restaurant_agent.session_store import clear_sessions

client = TestClient(app)


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


def test_sessions_flow(dummy_menu_item):
    resp = client.post("/api/sessions", json={"channel": "browser"})
    assert resp.status_code == 200
    data = resp.json()
    sess_id = data["session_id"]
    assert sess_id.startswith("sess_")

    resp = client.get(f"/api/sessions/{sess_id}")
    assert resp.status_code == 200
    assert resp.json()["session_id"] == sess_id

    resp = client.get(f"/api/sessions/{sess_id}/order")
    assert resp.status_code == 200
    assert resp.json()["session_id"] == sess_id

    resp = client.get("/api/sessions/invalid_id")
    assert resp.status_code == 404

    add_item(sess_id, dummy_menu_item)

    resp = client.post(f"/api/sessions/{sess_id}/confirm")
    assert resp.status_code == 400
    assert "customer name" in resp.json()["detail"]

    set_customer_name(sess_id, "Alice")

    resp = client.post(f"/api/sessions/{sess_id}/readback")
    assert resp.status_code == 200

    resp = client.post(f"/api/sessions/{sess_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["order"]["status"] == "confirmed"

    resp2 = client.post("/api/sessions", json={"channel": "browser"})
    sess_id_2 = resp2.json()["session_id"]
    resp = client.post(f"/api/sessions/{sess_id_2}/cancel")
    assert resp.status_code == 200
    assert resp.json()["order"]["status"] == "cancelled"

    resp = client.get("/api/debug/sessions/recent")
    assert resp.status_code == 200
    assert len(resp.json()["sessions"]) == 2

    resp = client.get(f"/api/debug/session/{sess_id}")
    assert resp.status_code == 200
    debug_data = resp.json()
    assert debug_data["session_id"] == sess_id
    assert debug_data["order_status"] == "confirmed"
    assert debug_data["customer_name"] == "Alice"
