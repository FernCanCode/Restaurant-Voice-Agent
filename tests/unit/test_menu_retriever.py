import pytest

from restaurant_agent.menu_retriever import search_menu
from restaurant_agent.schemas import CanonicalMenu, MenuItem, RestaurantMetadata


@pytest.fixture
def sample_menu():
    meta = RestaurantMetadata(
        name="Test", currency="USD", tax_rate=0.1, service_fee_rate=0.0
    )
    item1 = MenuItem(
        id="chicken_tacos",
        name="Chicken Tacos",
        category="Tacos",
        description="tasty tacos",
        base_price=5.0,
        available=True,
        source_text="",
        source_type="html",
    )
    item2 = MenuItem(
        id="lemonade",
        name="Lemonade",
        category="Drinks",
        description="fresh drink",
        base_price=2.0,
        available=True,
        source_text="",
        source_type="html",
        dietary_tags=["vegetarian"],
    )
    return CanonicalMenu(restaurant=meta, items=[item1, item2])


def test_search_menu_tacos(sample_menu, tmp_path):
    results = search_menu("tacos", sample_menu, tmp_path)
    assert len(results) > 0
    assert results[0].item_id == "chicken_tacos"


def test_search_menu_chicken_taco(sample_menu, tmp_path):
    results = search_menu("chicken taco", sample_menu, tmp_path)
    assert len(results) > 0
    assert results[0].item_id == "chicken_tacos"


def test_search_menu_lemonade(sample_menu, tmp_path):
    results = search_menu("lemonade", sample_menu, tmp_path)
    assert len(results) > 0
    assert results[0].item_id == "lemonade"


def test_search_menu_unknown(sample_menu, tmp_path):
    results = search_menu("pizza", sample_menu, tmp_path)
    assert len(results) == 0


def test_duplicate_results_removed(sample_menu, tmp_path):
    results = search_menu("Chicken Tacos", sample_menu, tmp_path)
    assert len([r for r in results if r.item_id == "chicken_tacos"]) == 1
