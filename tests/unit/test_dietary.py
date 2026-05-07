import pytest

from restaurant_agent.dietary import (
    check_allergen_info,
    find_dietary_items,
    summarize_dietary_answer,
)
from restaurant_agent.schemas import CanonicalMenu, MenuItem, RestaurantMetadata


@pytest.fixture
def sample_menu():
    meta = RestaurantMetadata(
        name="Test", currency="USD", tax_rate=0.1, service_fee_rate=0.0
    )
    item1 = MenuItem(
        id="black_bean_bowl",
        name="Black Bean Bowl",
        category="Mains",
        description="",
        base_price=10.0,
        available=True,
        source_text="",
        source_type="html",
        dietary_tags=["vegetarian", "vegan"],
        ingredients=["black beans", "rice", "corn", "salsa"],
    )
    item2 = MenuItem(
        id="quesadilla",
        name="Veggie Quesadilla",
        category="Mains",
        description="",
        base_price=9.0,
        available=True,
        source_text="",
        source_type="html",
        dietary_tags=["vegetarian"],
        allergens=["dairy", "wheat"],
    )
    return CanonicalMenu(restaurant=meta, items=[item1, item2])


def test_find_dietary_items(sample_menu):
    veg_items = find_dietary_items(sample_menu, "vegetarian")
    assert len(veg_items) == 2

    vegan_items = find_dietary_items(sample_menu, "vegan")
    assert len(vegan_items) == 1
    assert vegan_items[0].id == "black_bean_bowl"


def test_check_allergen_info(sample_menu):
    quesadilla = sample_menu.items[1]

    check = check_allergen_info(quesadilla, "dairy")
    assert check["has_allergen"] is True
    assert "Explicitly listed" in str(check["evidence"])

    check2 = check_allergen_info(quesadilla, "peanut")
    assert check2["has_allergen"] is False
    assert "Not listed" in str(check2["evidence"])


def test_summarize_dietary_answer(sample_menu):
    bowl = sample_menu.items[0]

    answer = summarize_dietary_answer(
        bowl, "Is the black bean bowl safe for a peanut allergy?"
    )
    assert "cannot guarantee it is peanut-free" in answer

    quesadilla = sample_menu.items[1]
    answer2 = summarize_dietary_answer(quesadilla, "Does this have dairy?")
    assert "Yes" in answer2
    assert "dairy" in answer2.lower()
