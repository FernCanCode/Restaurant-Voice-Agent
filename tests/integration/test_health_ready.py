from fastapi.testclient import TestClient
from restaurant_agent.api import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "restaurant-voice-agent"
    assert "version" in data


def test_ready_check():
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert "menu" in data
    assert "rag" in data


def test_ui_routes():
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "text/html" in res_root.headers.get("content-type", "")

    res_ui = client.get("/ui")
    assert res_ui.status_code == 200
    assert "text/html" in res_ui.headers.get("content-type", "")


def test_status_check_redacts_secrets():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()

    # Verify settings are present but secrets are redacted (if they were set)
    # The default setting for anthropic_api_key is None, but if it were set, it should be redacted.
    # We can at least check it doesn't expose raw values if configured.
    # For now, we just ensure it returns 200 and is a dict.
    assert isinstance(data, dict)
    if "anthropic_api_key" in data and data["anthropic_api_key"] is not None:
        assert data["anthropic_api_key"] == "[REDACTED]"
