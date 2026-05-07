from restaurant_agent.schemas import OrderLineItem, OrderState


def compute_line_subtotal(line_item: OrderLineItem) -> float:
    mod_total = sum(m.price_delta for m in line_item.known_modifications)
    subtotal = line_item.quantity * (line_item.base_unit_price + mod_total)
    return round(subtotal, 2)


def compute_order_totals(
    order: OrderState, tax_rate: float = 0.0825, service_fee_rate: float = 0.0
) -> OrderState:
    subtotal = 0.0
    for item in order.items:
        item.line_subtotal = compute_line_subtotal(item)
        item.line_total = item.line_subtotal
        subtotal += item.line_subtotal

    order.subtotal = round(subtotal, 2)
    order.tax = round(order.subtotal * tax_rate, 2)
    order.fees = round(order.subtotal * service_fee_rate, 2)
    order.total = round(order.subtotal + order.tax + order.fees, 2)

    return order


def format_money(amount: float, currency: str = "USD") -> str:
    if currency.upper() == "USD":
        return f"${amount:.2f}"
    return f"{amount:.2f} {currency}"
