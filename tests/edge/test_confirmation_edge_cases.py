import pytest

from restaurant_agent.order_store import (
    add_item,
    cancel_order,
    clear_orders,
    confirm_order,
    create_order,
    mark_readback_performed,
    set_customer_name,
)
from restaurant_agent.schemas import MenuItem


@pytest.fixture(autouse=True)
def setup_teardown():
    clear_orders()
    yield
    clear_orders()


@pytest.fixture
def taco_item():
    return MenuItem(
        id="taco",
        name="Taco",
        category="Tacos",
        description="",
        base_price=5.0,
        available=True,
        source_text="",
        source_type="html",
    )


def test_cannot_confirm_empty_order():
    create_order("sess1")
    set_customer_name("sess1", "Bob")
    mark_readback_performed("sess1")
    with pytest.raises(ValueError, match="Cannot confirm empty order"):
        confirm_order("sess1")


def test_cannot_confirm_without_name(taco_item):
    create_order("sess2")
    add_item("sess2", taco_item)
    mark_readback_performed("sess2")
    with pytest.raises(ValueError, match="Cannot confirm without customer name"):
        confirm_order("sess2")


def test_cannot_confirm_without_readback(taco_item):
    create_order("sess3")
    add_item("sess3", taco_item)
    set_customer_name("sess3", "Bob")
    with pytest.raises(ValueError, match="Cannot confirm without readback"):
        confirm_order("sess3")


def test_cannot_confirm_cancelled_order(taco_item):
    create_order("sess4")
    add_item("sess4", taco_item)
    set_customer_name("sess4", "Bob")
    mark_readback_performed("sess4")
    cancel_order("sess4")
    with pytest.raises(ValueError, match="Cannot confirm cancelled order"):
        confirm_order("sess4")


def test_cannot_confirm_already_confirmed_order(taco_item):
    create_order("sess5")
    add_item("sess5", taco_item)
    set_customer_name("sess5", "Bob")
    mark_readback_performed("sess5")
    confirm_order("sess5")

    with pytest.raises(ValueError, match="Order is already confirmed"):
        confirm_order("sess5")
