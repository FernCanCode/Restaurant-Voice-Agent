from fastapi.testclient import TestClient
from restaurant_agent.api import app

client = TestClient(app)


def test_request_without_id_gets_id():
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


def test_request_with_id_preserves_id():
    test_id = "test-req-123"
    response = client.get("/health", headers={"X-Request-ID": test_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == test_id
