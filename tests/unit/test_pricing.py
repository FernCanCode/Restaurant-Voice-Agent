from restaurant_agent.pricing import (
    compute_line_subtotal,
    compute_order_totals,
    format_money,
)
from restaurant_agent.schemas import (
    OrderLineItem,
    OrderState,
    OrderStatus,
    PricedModification,
)


def test_compute_line_subtotal():
    mod1 = PricedModification(name="extra meat", price_delta=2.0)
    item = OrderLineItem(
        line_item_id="line1",
        item_id="item1",
        item_name="Taco",
        quantity=2,
        base_unit_price=5.0,
        known_modifications=[mod1],
        special_instructions=["no onions"],  # should not affect price
        line_subtotal=0.0,
        line_total=0.0,
    )

    # (5.0 + 2.0) * 2 = 14.0
    assert compute_line_subtotal(item) == 14.0


def test_compute_order_totals():
    item1 = OrderLineItem(
        line_item_id="line1",
        item_id="item1",
        item_name="Taco",
        quantity=1,
        base_unit_price=10.0,
        known_modifications=[],
        line_subtotal=0.0,
        line_total=0.0,
    )
    order = OrderState(
        session_id="sess1",
        status=OrderStatus.active,
        currency="USD",
        readback_performed=False,
        items=[item1],
    )

    order = compute_order_totals(order, tax_rate=0.1, service_fee_rate=0.0)

    assert order.subtotal == 10.0
    assert order.tax == 1.0
    assert order.fees == 0.0
    assert order.total == 11.0


def test_format_money():
    assert format_money(12.3) == "$12.30"
    assert format_money(5) == "$5.00"
    assert format_money(12.3, currency="EUR") == "12.30 EUR"
