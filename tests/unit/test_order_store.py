import pytest

from restaurant_agent.order_store import (
    add_item,
    add_special_instruction,
    cancel_order,
    clear_orders,
    create_order,
    mark_readback_performed,
    remove_line_item,
    set_customer_name,
    update_line_item_quantity,
)
from restaurant_agent.schemas import MenuItem, OrderStatus, PricedModification


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


def test_create_order():
    order = create_order("sess1")
    assert order.status == OrderStatus.active
    assert order.total == 0.0


def test_add_item_and_remove(taco_item):
    order = create_order("sess1")
    order = add_item(
        "sess1", taco_item, quantity=2, known_modification_names=["extra meat"]
    )
    assert len(order.items) == 1
    assert order.items[0].quantity == 2
    assert order.items[0].known_modifications[0].name == "extra meat"

    assert order.subtotal == 14.0

    line_id = order.items[0].line_item_id
    order = remove_line_item("sess1", line_id)
    assert len(order.items) == 0
    assert order.subtotal == 0.0


def test_add_unknown_modification_is_not_priced(taco_item):
    order = create_order("sess2")
    order = add_item(
        "sess2", taco_item, quantity=1, known_modification_names=["extra queso"]
    )
    assert len(order.items) == 1
    assert len(order.items[0].known_modifications) == 0
    assert order.subtotal == 5.0


def test_special_instruction_stored_separately_not_priced(taco_item):
    order = create_order("sess3")
    order = add_item("sess3", taco_item, special_instructions=["no onions"])
    assert "no onions" in order.items[0].special_instructions
    assert order.subtotal == 5.0

    order = add_special_instruction("sess3", order.items[0].line_item_id, "extra spicy")
    assert "extra spicy" in order.items[0].special_instructions


def test_update_quantity(taco_item):
    order = create_order("sess4")
    order = add_item("sess4", taco_item, quantity=1)
    assert order.subtotal == 5.0

    order = update_line_item_quantity("sess4", order.items[0].line_item_id, 3)
    assert order.items[0].quantity == 3
    assert order.subtotal == 15.0


def test_set_customer_name_and_readback():
    order = create_order("sess5")
    order = set_customer_name("sess5", "Alice")
    assert order.customer_name == "Alice"

    assert order.readback_performed is False
    order = mark_readback_performed("sess5")
    assert order.readback_performed is True


def test_cancel_order():
    order = create_order("sess6")
    order = cancel_order("sess6")
    assert order.status == OrderStatus.cancelled
