import pytest
from restaurant_agent.schemas import CanonicalMenu, RestaurantMetadata, MenuItem
from restaurant_agent.menu_loader import (
    get_item_by_id,
    find_items_by_category,
    list_available_items,
    menu_to_lookup,
)


@pytest.fixture
def sample_menu():
    meta = RestaurantMetadata(
        name="Test", currency="USD", tax_rate=0.1, service_fee_rate=0.0
    )
    item1 = MenuItem(
        id="chicken_tacos",
        name="Chicken Tacos",
        category="Tacos",
        description="",
        base_price=5.0,
        available=True,
        source_text="",
        source_type="html",
    )
    item2 = MenuItem(
        id="soda",
        name="Soda",
        category="Drinks",
        description="",
        base_price=2.0,
        available=False,
        source_text="",
        source_type="html",
    )
    return CanonicalMenu(restaurant=meta, items=[item1, item2])


def test_get_item_by_id(sample_menu):
    item = get_item_by_id(sample_menu, "chicken_tacos")
    assert item is not None
    assert item.name == "Chicken Tacos"


def test_get_item_by_id_missing(sample_menu):
    item = get_item_by_id(sample_menu, "missing")
    assert item is None


def test_find_items_by_category(sample_menu):
    items = find_items_by_category(sample_menu, "Tacos")
    assert len(items) == 1
    assert items[0].id == "chicken_tacos"


def test_list_available_items(sample_menu):
    available = list_available_items(sample_menu)
    assert len(available) == 1
    assert available[0].id == "chicken_tacos"


def test_menu_to_lookup(sample_menu):
    lookup = menu_to_lookup(sample_menu)
    assert "chicken_tacos" in lookup
    assert "soda" in lookup
    assert lookup["chicken_tacos"].name == "Chicken Tacos"
