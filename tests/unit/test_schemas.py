import pytest
from pydantic import ValidationError
from restaurant_agent.schemas import (
    CanonicalMenu,
    RestaurantMetadata,
    MenuItem,
    PricedModification,
    OrderState,
    OrderLineItem,
    OrderStatus,
    CreateSessionRequest,
    AgentTurnRequest,
    Channel,
    MenuSearchRequest,
    DebugSessionResponse,
    DialogueMode,
)


def test_canonical_menu_creation():
    restaurant = RestaurantMetadata(
        name="Test", currency="USD", tax_rate=0.08, service_fee_rate=0.05
    )
    menu = CanonicalMenu(restaurant=restaurant)
    assert menu.restaurant.name == "Test"
    assert menu.items == []


def test_order_state_default_shape():
    order = OrderState(
        session_id="123",
        status=OrderStatus.active,
        currency="USD",
        readback_performed=False,
    )
    assert order.items == []
    assert order.subtotal == 0.0
    assert order.tax == 0.0
    assert order.fees == 0.0
    assert order.total == 0.0


def test_order_line_item_rejects_quantity_less_than_1():
    with pytest.raises(ValidationError):
        OrderLineItem(
            line_item_id="1",
            item_id="item1",
            item_name="Taco",
            quantity=0,
            base_unit_price=1.0,
            line_subtotal=1.0,
            line_total=1.0,
        )


def test_menu_item_rejects_negative_price():
    with pytest.raises(ValidationError):
        MenuItem(
            id="1",
            name="Taco",
            category="Food",
            description="A taco",
            base_price=-1.0,
            available=True,
            source_text="Taco",
            source_type="text",
        )


def test_priced_modification_rejects_negative_price():
    with pytest.raises(ValidationError):
        PricedModification(name="No onion", price_delta=-0.5)


def test_create_session_request_defaults():
    req = CreateSessionRequest()
    assert req.channel == Channel.browser


def test_agent_turn_request_accepts_metadata():
    req = AgentTurnRequest(session_id="123", utterance="hello", metadata={"foo": "bar"})
    assert req.metadata == {"foo": "bar"}


def test_menu_search_request_defaults():
    req = MenuSearchRequest(query="tacos")
    assert req.top_k == 5


def test_debug_session_response_can_include_twilio_sid():
    order = OrderState(
        session_id="123",
        status=OrderStatus.active,
        currency="USD",
        readback_performed=False,
    )
    resp = DebugSessionResponse(
        session_id="123",
        channel=Channel.twilio,
        twilio_call_sid="CA123",
        dialogue_mode=DialogueMode.GREETING,
        order_status=OrderStatus.active,
        order=order,
        degraded_llm=False,
        degraded_retrieval=False,
        request_id="req1",
    )
    assert resp.twilio_call_sid == "CA123"


def test_no_mutable_default_sharing():
    req1 = AgentTurnRequest(session_id="1", utterance="hello")
    req2 = AgentTurnRequest(session_id="2", utterance="hi")
    req1.metadata["key"] = "value"
    assert req2.metadata == {}
