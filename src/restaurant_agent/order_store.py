import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from restaurant_agent.pricing import compute_order_totals
from restaurant_agent.schemas import MenuItem, OrderLineItem, OrderState, OrderStatus

_ORDERS: Dict[str, OrderState] = {}


def create_order(session_id: str, currency: str = "USD") -> OrderState:
    order = OrderState(
        session_id=session_id,
        status=OrderStatus.active,
        currency=currency,
        readback_performed=False,
    )
    _ORDERS[session_id] = order
    return order


def get_order(session_id: str) -> Optional[OrderState]:
    return _ORDERS.get(session_id)


def update_order(order: OrderState) -> OrderState:
    order = compute_order_totals(order)
    _ORDERS[order.session_id] = order
    return order


def set_customer_name(session_id: str, customer_name: str) -> OrderState:
    order = get_order(session_id)
    if not order:
        raise ValueError(f"Order not found for session {session_id}")
    order.customer_name = customer_name
    return update_order(order)


def add_item(
    session_id: str,
    menu_item: MenuItem,
    quantity: int = 1,
    known_modification_names: Optional[List[str]] = None,
    special_instructions: Optional[List[str]] = None,
) -> OrderState:
    order = get_order(session_id)
    if not order:
        raise ValueError(f"Order not found for session {session_id}")

    if not menu_item.available:
        raise ValueError(f"Menu item {menu_item.id} is not available")

    if quantity <= 0:
        raise ValueError(f"Quantity must be positive, got {quantity}")

    line_item_id = f"line_{uuid.uuid4().hex[:8]}"

    valid_mods = []
    if known_modification_names:
        valid_mod_map = {m.name: m for m in menu_item.modifications}
        for mod_name in known_modification_names:
            if mod_name in valid_mod_map:
                valid_mods.append(valid_mod_map[mod_name])

    line_item = OrderLineItem(
        line_item_id=line_item_id,
        item_id=menu_item.id,
        item_name=menu_item.name,
        quantity=quantity,
        base_unit_price=menu_item.base_price,
        known_modifications=valid_mods,
        special_instructions=special_instructions or [],
        line_subtotal=0.0,
        line_total=0.0,
    )

    order.items.append(line_item)
    order.readback_performed = False
    return update_order(order)


def remove_line_item(session_id: str, line_item_id: str) -> OrderState:
    order = get_order(session_id)
    if not order:
        raise ValueError(f"Order not found for session {session_id}")

    if not order.items:
        raise ValueError("Cannot remove item from empty order")

    initial_len = len(order.items)
    order.items = [i for i in order.items if i.line_item_id != line_item_id]

    if len(order.items) == initial_len:
        raise ValueError(f"Line item {line_item_id} not found")

    order.readback_performed = False
    return update_order(order)


def update_line_item_quantity(
    session_id: str, line_item_id: str, quantity: int
) -> OrderState:
    order = get_order(session_id)
    if not order:
        raise ValueError(f"Order not found for session {session_id}")

    if quantity <= 0:
        raise ValueError(f"Quantity must be positive, got {quantity}")

    found = False
    for item in order.items:
        if item.line_item_id == line_item_id:
            item.quantity = quantity
            found = True
            break

    if not found:
        raise ValueError(f"Line item {line_item_id} not found")

    order.readback_performed = False
    return update_order(order)


def add_special_instruction(
    session_id: str, line_item_id: str, instruction: str
) -> OrderState:
    order = get_order(session_id)
    if not order:
        raise ValueError(f"Order not found for session {session_id}")

    found = False
    for item in order.items:
        if item.line_item_id == line_item_id:
            if instruction not in item.special_instructions:
                item.special_instructions.append(instruction)
            found = True
            break

    if not found:
        raise ValueError(f"Line item {line_item_id} not found")

    order.readback_performed = False
    return update_order(order)


def mark_readback_performed(session_id: str) -> OrderState:
    order = get_order(session_id)
    if not order:
        raise ValueError(f"Order not found for session {session_id}")
    order.readback_performed = True
    return update_order(order)


def confirm_order(session_id: str) -> OrderState:
    order = get_order(session_id)
    if not order:
        raise ValueError(f"Order not found for session {session_id}")

    if not order.items:
        raise ValueError("Cannot confirm empty order")

    if not order.customer_name:
        raise ValueError("Cannot confirm without customer name")

    if not order.readback_performed:
        raise ValueError("Cannot confirm without readback")

    if order.status == OrderStatus.cancelled:
        raise ValueError("Cannot confirm cancelled order")

    if order.status == OrderStatus.confirmed:
        raise ValueError("Order is already confirmed")

    order.status = OrderStatus.confirmed
    order.confirmation_id = f"CONF-{uuid.uuid4().hex[:6].upper()}"
    order.confirmed_at = datetime.now(timezone.utc).isoformat()
    return update_order(order)


def cancel_order(session_id: str) -> OrderState:
    order = get_order(session_id)
    if not order:
        raise ValueError(f"Order not found for session {session_id}")

    order.status = OrderStatus.cancelled
    return update_order(order)


def clear_orders() -> None:
    _ORDERS.clear()
