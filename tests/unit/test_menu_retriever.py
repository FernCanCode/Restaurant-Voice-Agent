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
        id="crispy_fish_tacos",
        name="Crispy Fish Tacos",
        category="Tacos",
        description="crispy fish tacos",
        base_price=6.5,
        available=True,
        source_text="",
        source_type="html",
    )
    item3 = MenuItem(
        id="street_corn",
        name="Street Corn",
        category="Sides",
        description="corn with cotija",
        base_price=4.0,
        available=True,
        source_text="",
        source_type="html",
    )
    item4 = MenuItem(
        id="black_bean_bowl",
        name="Black Bean Bowl",
        category="Bowls",
        description="bean bowl",
        base_price=9.0,
        available=True,
        source_text="",
        source_type="html",
    )
    item5 = MenuItem(
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
    return CanonicalMenu(restaurant=meta, items=[item1, item2, item3, item4, item5])


def test_search_menu_tacos(sample_menu, tmp_path):
    results = search_menu("tacos", sample_menu, tmp_path)
    item_ids = {result.item_id for result in results}
    assert "chicken_tacos" in item_ids
    assert "crispy_fish_tacos" in item_ids
    assert "street_corn" not in item_ids
    assert "black_bean_bowl" not in item_ids


def test_search_menu_explicit_taco_question_excludes_sides(sample_menu, tmp_path):
    results = search_menu("What tacos do you have?", sample_menu, tmp_path)
    item_ids = {result.item_id for result in results}
    assert "chicken_tacos" in item_ids
    assert "crispy_fish_tacos" in item_ids
    assert "street_corn" not in item_ids
    assert "black_bean_bowl" not in item_ids


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
