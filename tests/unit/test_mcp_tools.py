import pytest

from restaurant_agent.mcp_server import call_tool, list_tools
from restaurant_agent.order_store import (
    clear_orders,
    create_order,
    mark_readback_performed,
    set_customer_name,
)
from restaurant_agent.schemas import ToolStatus
from restaurant_agent.session_store import clear_sessions, create_session


@pytest.fixture(autouse=True)
def setup_teardown():
    clear_sessions()
    clear_orders()
    yield
    clear_sessions()
    clear_orders()


# ── list_tools ──────────────────────────────────────────────────────────

REQUIRED_TOOL_NAMES = [
    "search_menu",
    "get_menu_item",
    "check_dietary_info",
    "add_order_item",
    "remove_order_item",
    "update_order_item",
    "get_order_summary",
    "compute_total",
    "confirm_order",
    "cancel_order",
]


def test_list_tools_returns_all_10():
    tools = list_tools()
    assert len(tools) == 10
    names = [t["name"] for t in tools]
    for required in REQUIRED_TOOL_NAMES:
        assert required in names, f"Missing tool: {required}"


def test_list_tools_metadata_shape():
    """Each tool should expose name, description, and required_arguments."""
    for tool in list_tools():
        assert "name" in tool
        assert "description" in tool
        assert "required_arguments" in tool
        assert isinstance(tool["required_arguments"], list)


# ── error handling ──────────────────────────────────────────────────────


def test_unknown_tool_returns_error():
    res = call_tool("fake_tool", {})
    assert res["status"] == ToolStatus.error.value
    assert "Unknown tool" in res["error"]
    assert res["tool_name"] == "fake_tool"
    assert res["result"] is None


def test_missing_argument_returns_error():
    res = call_tool("search_menu", {})
    assert res["status"] == ToolStatus.error.value
    assert "Missing required argument" in res["error"]


def test_response_shape():
    """Every call_tool result must contain the five required keys."""
    res = call_tool("fake_tool", {}, request_id="req_123")
    for key in ("tool_name", "status", "result", "error", "request_id"):
        assert key in res
    assert res["request_id"] == "req_123"


# ── search_menu ─────────────────────────────────────────────────────────


def test_search_menu_returns_taco_results():
    res = call_tool("search_menu", {"query": "tacos", "top_k": 5})
    assert res["status"] == ToolStatus.success.value
    assert isinstance(res["result"], list)
    assert len(res["result"]) > 0
    item_ids = [r["item_id"] for r in res["result"]]
    assert "chicken_tacos" in item_ids


# ── get_menu_item ───────────────────────────────────────────────────────


def test_get_menu_item_returns_chicken_tacos():
    res = call_tool("get_menu_item", {"item_id": "chicken_tacos"})
    assert res["status"] == ToolStatus.success.value
    assert res["result"]["id"] == "chicken_tacos"
    assert res["result"]["name"] == "Chicken Tacos"


def test_get_menu_item_missing_item():
    res = call_tool("get_menu_item", {"item_id": "nonexistent_item"})
    assert res["status"] == ToolStatus.error.value
    assert "Item not found" in res["error"]


# ── check_dietary_info ──────────────────────────────────────────────────


def test_check_dietary_info_peanut_cautious():
    res = call_tool(
        "check_dietary_info",
        {
            "item_id": "black_bean_bowl",
            "question": "Is this safe for a peanut allergy?",
            "allergen": "peanuts",
        },
    )
    assert res["status"] == ToolStatus.success.value
    answer = res["result"]["answer"].lower()
    # Must be cautious — never guarantee safety
    assert "guarantee" in answer or "cannot" in answer


# ── add_order_item ──────────────────────────────────────────────────────


def test_add_order_item_basic():
    sess = create_session()
    create_order(sess.session_id)

    res = call_tool(
        "add_order_item",
        {
            "session_id": sess.session_id,
            "item_id": "chicken_tacos",
            "quantity": 2,
        },
    )
    assert res["status"] == ToolStatus.success.value
    assert len(res["result"]["items"]) == 1
    assert res["result"]["items"][0]["quantity"] == 2


def test_add_order_item_with_priced_modification():
    """Using carnitas_burrito with 'add guacamole' (+$2.00)."""
    sess = create_session()
    create_order(sess.session_id)

    res = call_tool(
        "add_order_item",
        {
            "session_id": sess.session_id,
            "item_id": "carnitas_burrito",
            "quantity": 1,
            "known_modification_names": ["add guacamole"],
        },
    )
    assert res["status"] == ToolStatus.success.value
    item = res["result"]["items"][0]
    assert len(item["known_modifications"]) == 1
    assert item["known_modifications"][0]["name"] == "add guacamole"
    # base 11.0 + 2.0 guac = 13.0
    assert item["line_subtotal"] == 13.0


def test_add_order_item_with_special_instruction_not_priced():
    sess = create_session()
    create_order(sess.session_id)

    res = call_tool(
        "add_order_item",
        {
            "session_id": sess.session_id,
            "item_id": "chicken_tacos",
            "quantity": 1,
            "special_instructions": ["no onions"],
        },
    )
    assert res["status"] == ToolStatus.success.value
    item = res["result"]["items"][0]
    assert "no onions" in item["special_instructions"]
    # Special instructions must not change price: base 8.5
    assert item["line_subtotal"] == 8.5


# ── remove_order_item ──────────────────────────────────────────────────


def test_remove_order_item():
    sess = create_session()
    create_order(sess.session_id)
    add_res = call_tool(
        "add_order_item",
        {"session_id": sess.session_id, "item_id": "chicken_tacos", "quantity": 1},
    )
    line_item_id = add_res["result"]["items"][0]["line_item_id"]

    res = call_tool(
        "remove_order_item",
        {"session_id": sess.session_id, "line_item_id": line_item_id},
    )
    assert res["status"] == ToolStatus.success.value
    assert len(res["result"]["items"]) == 0


# ── update_order_item ──────────────────────────────────────────────────


def test_update_order_item_quantity():
    sess = create_session()
    create_order(sess.session_id)
    add_res = call_tool(
        "add_order_item",
        {"session_id": sess.session_id, "item_id": "chicken_tacos", "quantity": 1},
    )
    line_item_id = add_res["result"]["items"][0]["line_item_id"]

    res = call_tool(
        "update_order_item",
        {"session_id": sess.session_id, "line_item_id": line_item_id, "quantity": 4},
    )
    assert res["status"] == ToolStatus.success.value
    assert res["result"]["items"][0]["quantity"] == 4


def test_update_order_item_special_instructions():
    sess = create_session()
    create_order(sess.session_id)
    add_res = call_tool(
        "add_order_item",
        {"session_id": sess.session_id, "item_id": "chicken_tacos", "quantity": 1},
    )
    line_item_id = add_res["result"]["items"][0]["line_item_id"]

    res = call_tool(
        "update_order_item",
        {
            "session_id": sess.session_id,
            "line_item_id": line_item_id,
            "special_instructions_to_add": ["extra salsa"],
        },
    )
    assert res["status"] == ToolStatus.success.value
    assert "extra salsa" in res["result"]["items"][0]["special_instructions"]


# ── get_order_summary ──────────────────────────────────────────────────


def test_get_order_summary():
    sess = create_session()
    create_order(sess.session_id)
    call_tool(
        "add_order_item",
        {
            "session_id": sess.session_id,
            "item_id": "chicken_tacos",
            "quantity": 2,
            "special_instructions": ["no onions"],
        },
    )

    res = call_tool("get_order_summary", {"session_id": sess.session_id})
    assert res["status"] == ToolStatus.success.value
    assert "2x Chicken Tacos" in res["result"]["summary"]
    assert "no onions" in res["result"]["summary"]
    assert "order" in res["result"]


# ── compute_total ──────────────────────────────────────────────────────


def test_compute_total_deterministic():
    sess = create_session()
    create_order(sess.session_id)
    call_tool(
        "add_order_item",
        {"session_id": sess.session_id, "item_id": "chicken_tacos", "quantity": 1},
    )

    res = call_tool("compute_total", {"session_id": sess.session_id})
    assert res["status"] == ToolStatus.success.value
    result = res["result"]
    assert result["subtotal"] == 8.5
    assert result["total"] > result["subtotal"]  # tax applied
    assert "currency" in result
    assert "formatted_total" in result


# ── confirm_order ──────────────────────────────────────────────────────


def test_confirm_order_enforces_rules():
    sess = create_session()
    create_order(sess.session_id)
    call_tool(
        "add_order_item",
        {"session_id": sess.session_id, "item_id": "chicken_tacos", "quantity": 1},
    )

    # Cannot confirm without customer name
    res = call_tool("confirm_order", {"session_id": sess.session_id})
    assert res["status"] == ToolStatus.error.value
    assert "customer name" in res["error"].lower()

    set_customer_name(sess.session_id, "Alice")

    # Cannot confirm without readback
    res = call_tool("confirm_order", {"session_id": sess.session_id})
    assert res["status"] == ToolStatus.error.value
    assert "readback" in res["error"].lower()

    mark_readback_performed(sess.session_id)

    # Now it should succeed
    res = call_tool("confirm_order", {"session_id": sess.session_id})
    assert res["status"] == ToolStatus.success.value
    assert res["result"]["confirmation_id"] is not None
    assert res["result"]["order"]["status"] == "confirmed"


# ── cancel_order ───────────────────────────────────────────────────────


def test_cancel_order():
    sess = create_session()
    create_order(sess.session_id)
    res = call_tool("cancel_order", {"session_id": sess.session_id})
    assert res["status"] == ToolStatus.success.value
    assert res["result"]["status"] == "cancelled"
