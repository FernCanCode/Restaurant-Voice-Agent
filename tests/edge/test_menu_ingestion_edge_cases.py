import pytest
from restaurant_agent.menu_ingestion import ingest_menu_html, ingest_menu_file


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        ingest_menu_file("nonexistent_menu.html")


def test_unsupported_extension_raises(tmp_path):
    # To test unsupported extension, create a dummy .txt file
    txt_file = tmp_path / "menu.txt"
    txt_file.write_text("dummy")
    with pytest.raises(ValueError, match="Unsupported file extension"):
        ingest_menu_file(txt_file)


def test_empty_html_raises():
    with pytest.raises(ValueError, match="Empty HTML"):
        ingest_menu_html("   \n   ")


def test_missing_price_raises():
    html = """
    <div id="restaurant-metadata" data-name="Test" data-currency="USD" data-tax-rate="0.0"></div>
    <div class="category" data-category="Tacos">
        <div class="menu-item" data-id="test">
        </div>
    </div>
    """
    with pytest.raises(ValueError, match="Menu item missing price"):
        ingest_menu_html(html)


def test_missing_id_raises():
    html = """
    <div id="restaurant-metadata" data-name="Test" data-currency="USD" data-tax-rate="0.0"></div>
    <div class="category" data-category="Tacos">
        <div class="menu-item" data-price="10.0">
        </div>
    </div>
    """
    with pytest.raises(ValueError, match="Menu item missing id"):
        ingest_menu_html(html)
