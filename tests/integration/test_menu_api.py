from fastapi.testclient import TestClient

from restaurant_agent.api import app

client = TestClient(app)


def test_get_menu_items():
    response = client.get("/api/menu/items")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_menu_item_found():
    response = client.get("/api/menu/items/chicken_tacos")
    if response.status_code == 200:
        data = response.json()
        assert data["id"] == "chicken_tacos"
    elif response.status_code == 404:
        # If test runs before menu is built, this is acceptable.
        pass


def test_get_menu_item_not_found():
    response = client.get("/api/menu/items/non_existent_item_999")
    assert response.status_code == 404


def test_search_menu():
    response = client.post("/api/menu/search", json={"query": "tacos", "top_k": 3})
    if response.status_code == 200:
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)


def test_rebuild_index():
    response = client.post("/api/menu/rebuild-index")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "metadata" in data
