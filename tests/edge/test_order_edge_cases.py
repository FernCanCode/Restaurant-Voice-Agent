import pytest

from restaurant_agent.mcp_server import call_tool
from restaurant_agent.order_store import (
    add_item,
    clear_orders,
    create_order,
    remove_line_item,
    update_line_item_quantity,
)
from restaurant_agent.schemas import MenuItem, ToolStatus


@pytest.fixture(autouse=True)
def setup_teardown():
    clear_orders()
    yield
    clear_orders()


@pytest.fixture
def available_item():
    return MenuItem(
        id="item1",
        name="Available Item",
        category="Cat",
        description="",
        base_price=5.0,
        available=True,
        source_text="",
        source_type="html",
    )


@pytest.fixture
def unavailable_item():
    return MenuItem(
        id="item2",
        name="Unavailable Item",
        category="Cat",
        description="",
        base_price=5.0,
        available=False,
        source_text="",
        source_type="html",
    )


def test_missing_session_raises_exception(available_item):
    with pytest.raises(ValueError, match="Order not found"):
        add_item("invalid_sess", available_item)


def test_missing_line_item_raises_exception():
    create_order("sess1")
    with pytest.raises(ValueError, match="Cannot remove item from empty order"):
        remove_line_item("sess1", "invalid_line")


def test_quantity_zero_rejected(available_item):
    create_order("sess2")
    with pytest.raises(ValueError, match="Quantity must be positive"):
        add_item("sess2", available_item, quantity=0)

    order = add_item("sess2", available_item, quantity=1)
    with pytest.raises(ValueError, match="Quantity must be positive"):
        update_line_item_quantity("sess2", order.items[0].line_item_id, 0)


def test_negative_quantity_rejected(available_item):
    create_order("sess3")
    with pytest.raises(ValueError, match="Quantity must be positive"):
        add_item("sess3", available_item, quantity=-1)


def test_removing_item_from_empty_order_rejected():
    create_order("sess4")
    with pytest.raises(ValueError, match="Cannot remove item from empty order"):
        remove_line_item("sess4", "line_123")


def test_add_unavailable_item_rejected(unavailable_item):
    create_order("sess5")
    with pytest.raises(ValueError, match="is not available"):
        add_item("sess5", unavailable_item)


def test_mcp_missing_menu_item_returns_error():
    res = call_tool(
        "add_order_item",
        {"session_id": "sess1", "item_id": "invalid_item_id_999", "quantity": 1},
    )
    assert res["status"] == ToolStatus.error.value
    assert "Item not found" in res["error"]


def test_mcp_remove_requires_line_item_id():
    res = call_tool(
        "remove_order_item",
        {
            "session_id": "sess1"
            # missing line_item_id
        },
    )
    assert res["status"] == ToolStatus.error.value
    assert "Missing required argument" in res["error"]


def test_mcp_remove_ambiguous_name_not_supported():
    # passing item_name instead of line_item_id
    res = call_tool("remove_order_item", {"session_id": "sess1", "item_name": "Taco"})
    assert res["status"] == ToolStatus.error.value
    assert "Missing required argument" in res["error"]
