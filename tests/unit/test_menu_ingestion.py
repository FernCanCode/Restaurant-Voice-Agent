import pytest
from pathlib import Path
from restaurant_agent.menu_ingestion import ingest_menu_html, build_menu_from_fixture

FIXTURE_PATH = Path("data/raw/sample_restaurant_menu.html")


def test_ingest_menu_html():
    if not FIXTURE_PATH.exists():
        pytest.skip("Fixture not available")

    html = FIXTURE_PATH.read_text(encoding="utf-8")
    menu = ingest_menu_html(html)

    assert menu.restaurant.name == "Cedar & Lime Taqueria"
    assert menu.restaurant.tax_rate == 0.0825
    assert len(menu.items) >= 10

    # Check Chicken Tacos
    chicken_tacos = next(i for i in menu.items if i.name == "Chicken Tacos")
    assert "chicken taco" in chicken_tacos.aliases
    assert "onions" in chicken_tacos.ingredients
    assert len(chicken_tacos.modifications) > 0
    mod_names = [m.name for m in chicken_tacos.modifications]
    assert "extra queso" not in mod_names

    # Check Black Bean Bowl
    bowl = next(i for i in menu.items if i.name == "Black Bean Bowl")
    assert bowl.name == "Black Bean Bowl"

    # Check vegetarian
    veg_items = [
        i for i in menu.items if "vegetarian" in [d.lower() for d in i.dietary_tags]
    ]
    assert len(veg_items) >= 2


def test_build_menu_from_fixture(tmp_path):
    if not FIXTURE_PATH.exists():
        pytest.skip("Fixture not available")

    out_path = tmp_path / "menu.json"
    menu = build_menu_from_fixture(FIXTURE_PATH, out_path)

    assert out_path.exists()
    assert len(menu.items) >= 10
