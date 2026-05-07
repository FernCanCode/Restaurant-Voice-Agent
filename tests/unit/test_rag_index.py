import json
import sys

import pytest

from restaurant_agent.rag_index import build_menu_chunks, build_rag_index
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
        description="",
        base_price=5.0,
        available=True,
        source_text="HTML",
        source_type="html",
    )
    return CanonicalMenu(restaurant=meta, items=[item1])


def test_build_menu_chunks(sample_menu):
    chunks = build_menu_chunks(sample_menu)
    assert len(chunks) == 1
    assert chunks[0]["item_name"] == "Chicken Tacos"
    assert chunks[0]["category"] == "Tacos"
    assert "Chicken Tacos" in chunks[0]["retrieval_text"]
    assert chunks[0]["source_text"] == "HTML"


def test_build_rag_index_degraded_mode(sample_menu, tmp_path, monkeypatch):
    # Force import error for sentence-transformers to test degraded mode safely
    def raise_import_error(*args, **kwargs):
        raise ImportError("No module named 'sentence_transformers'")

    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    menu_path = tmp_path / "menu.json"
    index_dir = tmp_path / "index"

    menu_path.write_text(sample_menu.model_dump_json())

    meta = build_rag_index(menu_path, index_dir, allow_embedding_failure=True)

    assert meta["degraded_mode"] is True
    assert "vector" not in meta["retrieval_modes_available"]

    chunks_path = index_dir / "menu_chunks.json"
    assert chunks_path.exists()
    chunks = json.loads(chunks_path.read_text())
    assert len(chunks) == 1

    meta_path = index_dir / "menu_metadata.json"
    assert meta_path.exists()
