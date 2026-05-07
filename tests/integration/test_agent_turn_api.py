import pytest
from fastapi.testclient import TestClient
from restaurant_agent.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_start_session_returns_greeting():
    response = client.post("/api/sessions", json={"channel": "browser"})
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"]
    assert "Welcome" in data["agent_text"]
    assert data["request_id"]


def test_turn_menu_question_rag():
    # start session
    sess = client.post("/api/sessions", json={"channel": "browser"}).json()
    session_id = sess["session_id"]

    # process turn
    turn_req = {
        "session_id": session_id,
        "utterance": "What tacos do you have?",
        "channel": "browser",
        "metadata": {},
    }
    response = client.post("/api/turn", json=turn_req)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "search_menu"
    assert len(data["tool_calls"]) > 0
    assert data["tool_calls"][0]["tool_name"] == "search_menu"
    assert data["tool_calls"][0]["status"] == "success"
    assert "taco" in data["agent_text"].lower()


def test_turn_add_chicken_tacos_updates_order():
    sess = client.post("/api/sessions", json={"channel": "browser"}).json()
    session_id = sess["session_id"]

    turn_req = {
        "session_id": session_id,
        "utterance": "Add two chicken tacos",
        "channel": "browser",
        "metadata": {},
    }
    response = client.post("/api/turn", json=turn_req)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "add_order_item"
    assert data["order"]["items"][0]["item_id"] == "chicken_tacos"
    assert data["order"]["items"][0]["quantity"] == 2


def test_turn_unsupported_modification_asks_clarification():
    sess = client.post("/api/sessions", json={"channel": "browser"}).json()
    session_id = sess["session_id"]

    turn_req = {
        "session_id": session_id,
        "utterance": "Add one chicken taco with extra queso",
        "channel": "browser",
        "metadata": {},
    }
    response = client.post("/api/turn", json=turn_req)
    assert response.status_code == 200
    data = response.json()
    # It should not have added the item yet
    assert len(data["order"]["items"]) == 0
    assert "extra queso" in data["agent_text"].lower()


def test_turn_total_request_returns_total():
    sess = client.post("/api/sessions", json={"channel": "browser"}).json()
    session_id = sess["session_id"]

    client.post(
        "/api/turn",
        json={
            "session_id": session_id,
            "utterance": "Add two chicken tacos",
            "channel": "browser",
            "metadata": {},
        },
    )

    turn_req = {
        "session_id": session_id,
        "utterance": "What is my total?",
        "channel": "browser",
        "metadata": {},
    }
    response = client.post("/api/turn", json=turn_req)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "compute_total"
    assert "total" in data["agent_text"].lower()


def test_missing_session_returns_404():
    turn_req = {
        "session_id": "invalid_session",
        "utterance": "Hello",
        "channel": "browser",
        "metadata": {},
    }
    response = client.post("/api/turn", json=turn_req)
    assert response.status_code == 404
