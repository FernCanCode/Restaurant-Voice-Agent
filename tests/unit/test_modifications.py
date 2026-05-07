import pytest

from restaurant_agent.order_store import add_item, clear_orders, create_order
from restaurant_agent.schemas import MenuItem, PricedModification


@pytest.fixture(autouse=True)
def setup_teardown():
    clear_orders()
    yield
    clear_orders()


@pytest.fixture
def taco_item():
    mod1 = PricedModification(name="extra meat", price_delta=2.0)
    return MenuItem(
        id="taco",
        name="Taco",
        category="Tacos",
        description="",
        base_price=5.0,
        available=True,
        modifications=[mod1],
        source_text="",
        source_type="html",
    )


def test_no_onions_special_instruction(taco_item):
    order = create_order("sess1")
    order = add_item("sess1", taco_item, special_instructions=["no onions"])
    assert len(order.items) == 1
    assert "no onions" in order.items[0].special_instructions
    assert order.items[0].line_subtotal == 5.0


def test_extra_queso_not_priced_when_unsupported(taco_item):
    order = create_order("sess2")
    order = add_item("sess2", taco_item, known_modification_names=["extra queso"])
    assert len(order.items[0].known_modifications) == 0
    assert order.items[0].line_subtotal == 5.0


def test_known_modification_priced(taco_item):
    order = create_order("sess3")
    order = add_item("sess3", taco_item, known_modification_names=["extra meat"])
    assert len(order.items[0].known_modifications) == 1
    assert order.items[0].line_subtotal == 7.0


def test_extra_queso_as_special_instruction_stored(taco_item):
    """extra queso passed as special_instructions is stored and never priced."""
    order = create_order("sess4")
    order = add_item("sess4", taco_item, special_instructions=["extra queso"])
    assert "extra queso" in order.items[0].special_instructions
    # Must not affect price
    assert order.items[0].line_subtotal == 5.0
