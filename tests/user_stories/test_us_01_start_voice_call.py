import pytest
from fastapi.testclient import TestClient
from restaurant_agent.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.mark.user_story("US-01")
def test_us_01_start_voice_call():
    # 1. GET / returns HTTP 200 and required strings
    html_res = client.get("/")
    assert html_res.status_code == 200
    html_text = html_res.text
    assert "Restaurant Voice Ordering Agent" in html_text
    assert "Start Voice Order" in html_text

    # 2. POST /api/browser/start-call returns greeting, empty order, etc
    start_res = client.post("/api/browser/start-call", json={})
    assert start_res.status_code == 200

    data = start_res.json()
    assert "Welcome" in data["agent_text"]
    assert data["session_id"]
    assert "request_id" in data

    # 3. Order should be empty and total 0.0
    order = data["order"]
    assert len(order["items"]) == 0
    assert order["total"] == 0.0
