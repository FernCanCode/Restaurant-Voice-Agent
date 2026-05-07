from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


# 1. Common enums
class Channel(str, Enum):
    browser = "browser"
    twilio = "twilio"
    api = "api"


class OrderStatus(str, Enum):
    active = "active"
    confirmed = "confirmed"
    cancelled = "cancelled"


class DialogueMode(str, Enum):
    GREETING = "GREETING"
    TAKING_ORDER = "TAKING_ORDER"
    CLARIFYING = "CLARIFYING"
    READBACK = "READBACK"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class ToolStatus(str, Enum):
    success = "success"
    error = "error"
    clarification_required = "clarification_required"


class RetrievalMode(str, Enum):
    hybrid = "hybrid"
    vector = "vector"
    lexical = "lexical"
    structured = "structured"
    degraded = "degraded"


# 2. Menu schemas
class PricedModification(BaseModel):
    name: str
    price_delta: float = Field(ge=0.0)


class MenuItem(BaseModel):
    id: str
    name: str
    aliases: List[str] = Field(default_factory=list)
    category: str
    description: str
    base_price: float = Field(ge=0.0)
    available: bool
    ingredients: List[str] = Field(default_factory=list)
    dietary_tags: List[str] = Field(default_factory=list)
    allergens: List[str] = Field(default_factory=list)
    modifications: List[PricedModification] = Field(default_factory=list)
    source_text: str
    source_type: str


class RestaurantMetadata(BaseModel):
    name: str
    currency: str
    tax_rate: float = Field(ge=0.0)
    service_fee_rate: float = Field(ge=0.0)


class CanonicalMenu(BaseModel):
    restaurant: RestaurantMetadata
    items: List[MenuItem] = Field(default_factory=list)


# 3. Order schemas
class OrderLineItem(BaseModel):
    line_item_id: str
    item_id: str
    item_name: str
    quantity: int = Field(ge=1)
    base_unit_price: float = Field(ge=0.0)
    known_modifications: List[PricedModification] = Field(default_factory=list)
    special_instructions: List[str] = Field(default_factory=list)
    line_subtotal: float = Field(ge=0.0)
    line_total: float = Field(ge=0.0)


class OrderState(BaseModel):
    session_id: str
    customer_name: Optional[str] = None
    status: OrderStatus
    items: List[OrderLineItem] = Field(default_factory=list)
    subtotal: float = Field(default=0.0, ge=0.0)
    tax: float = Field(default=0.0, ge=0.0)
    fees: float = Field(default=0.0, ge=0.0)
    total: float = Field(default=0.0, ge=0.0)
    currency: str
    readback_performed: bool
    confirmed_at: Optional[str] = None
    confirmation_id: Optional[str] = None


# 4. Dialogue/session schemas
class DialogueTurn(BaseModel):
    role: str
    content: str
    timestamp: str
    request_id: Optional[str] = None


class DialogueState(BaseModel):
    session_id: str
    channel: Channel
    twilio_call_sid: Optional[str] = None
    dialogue_mode: DialogueMode
    pending_action: Optional[str] = None
    pending_question: Optional[str] = None
    last_user_utterance: Optional[str] = None
    last_agent_response: Optional[str] = None
    last_intent: Optional[str] = None
    last_mentioned_item_id: Optional[str] = None
    last_retrieved_candidates: List[Any] = Field(default_factory=list)
    awaiting_final_confirmation: bool
    order_readback_required: bool
    turns: List[DialogueTurn] = Field(default_factory=list)
    degraded_llm: bool
    degraded_retrieval: bool
    request_ids: List[str] = Field(default_factory=list)


# 5. API request/response schemas
class CreateSessionRequest(BaseModel):
    channel: Channel = Channel.browser
    caller_id: Optional[str] = None


class CreateSessionResponse(BaseModel):
    session_id: str
    dialogue_mode: DialogueMode
    agent_text: str
    order: OrderState
    next_action: str
    request_id: str


class AgentTurnRequest(BaseModel):
    session_id: str
    utterance: str
    channel: Channel = Channel.browser
    speech_confidence: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolCallSummary(BaseModel):
    tool_name: str
    status: ToolStatus
    summary: str


class RetrievalSummary(BaseModel):
    used: bool
    mode: RetrievalMode
    top_results: List[Any] = Field(default_factory=list)
    confidence: float


class AgentTurnResponse(BaseModel):
    session_id: str
    dialogue_mode: DialogueMode
    intent: Optional[str] = None
    agent_text: str
    speak: bool
    order: OrderState
    tool_calls: List[ToolCallSummary] = Field(default_factory=list)
    retrieval: RetrievalSummary
    requires_user_response: bool
    next_action: str
    degraded_mode: bool
    request_id: str


class MenuSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    filters: Dict[str, Any] = Field(default_factory=dict)


class MenuSearchResult(BaseModel):
    item_id: str
    name: str
    category: str
    description: str
    price: float = Field(ge=0.0)
    score: float
    source_text: str


class MenuSearchResponse(BaseModel):
    query: str
    results: List[MenuSearchResult] = Field(default_factory=list)
    retrieval_mode: RetrievalMode
    confidence: float
    degraded_mode: bool
    request_id: str


# 6. Debug/session observability schemas
class RecentSessionSummary(BaseModel):
    session_id: str
    channel: Channel
    twilio_call_sid: Optional[str] = None
    order_status: OrderStatus
    customer_name: Optional[str] = None
    total: float = Field(ge=0.0)
    confirmation_id: Optional[str] = None


class RecentSessionsResponse(BaseModel):
    sessions: List[RecentSessionSummary] = Field(default_factory=list)
    request_id: str


class DebugSessionResponse(BaseModel):
    session_id: str
    channel: Channel
    twilio_call_sid: Optional[str] = None
    dialogue_mode: DialogueMode
    customer_name: Optional[str] = None
    order_status: OrderStatus
    order: OrderState
    recent_tool_calls: List[ToolCallSummary] = Field(default_factory=list)
    recent_retrievals: List[RetrievalSummary] = Field(default_factory=list)
    degraded_llm: bool
    degraded_retrieval: bool
    request_id: str


# 7. Health/readiness schemas
class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadinessComponent(BaseModel):
    status: str
    details: Optional[str] = None


class ReadyResponse(BaseModel):
    status: str
    components: Dict[str, ReadinessComponent] = Field(default_factory=dict)
    degraded_modes: Dict[str, bool] = Field(default_factory=dict)
    request_id: Optional[str] = None
