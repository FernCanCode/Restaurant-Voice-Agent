from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from typing import Dict, Any, cast

from restaurant_agent import __version__
from restaurant_agent.config import get_settings
from restaurant_agent.middleware import RequestIDMiddleware
from restaurant_agent.security import redact_secrets
from restaurant_agent.schemas import (
    AgentTurnRequest,
    AgentTurnResponse,
    Channel,
    CreateSessionRequest,
    CreateSessionResponse,
    DebugSessionResponse,
    DialogueMode,
    MenuSearchRequest,
    MenuSearchResponse,
    RecentSessionsResponse,
    RecentSessionSummary,
    RetrievalMode,
)
from restaurant_agent import agent
from restaurant_agent.menu_loader import load_menu, list_available_items, get_item_by_id
from restaurant_agent.menu_retriever import search_menu
from restaurant_agent.rag_index import build_rag_index, load_rag_metadata
from restaurant_agent.session_store import (
    get_session,
    set_dialogue_mode,
    list_recent_sessions,
)
from restaurant_agent.order_store import (
    get_order,
    mark_readback_performed,
    confirm_order,
    cancel_order,
)

from restaurant_agent.web import render_browser_ui

app = FastAPI(title="restaurant-voice-agent")
app.add_middleware(RequestIDMiddleware)


@app.get("/", response_class=HTMLResponse)
@app.get("/ui", response_class=HTMLResponse)
def get_browser_ui() -> HTMLResponse:
    html = render_browser_ui()
    return HTMLResponse(content=html, status_code=200)


@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {"status": "ok", "service": "restaurant-voice-agent", "version": __version__}


@app.get("/ready")
def readiness_check() -> Dict[str, Any]:
    # Phase 1: scaffolded statuses
    return {
        "menu": "ready",
        "rag": "ready",
        "mcp": "ready",
        "anthropic": "ready",
        "twilio": "ready",
        "browser_voice": "ready",
        "degraded_modes": False,
    }


@app.get("/api/status")
def status_check() -> Dict[str, Any]:
    settings = get_settings().model_dump()
    return cast(Dict[str, Any], redact_secrets(settings))


@app.get("/api/menu/items")
def get_menu_items() -> Any:
    settings = get_settings()
    try:
        menu = load_menu(settings.menu_data_path)
    except FileNotFoundError:
        return []
    items = list_available_items(menu)
    return [i.model_dump() for i in items]


@app.get("/api/menu/items/{item_id}")
def get_menu_item(item_id: str) -> Any:
    settings = get_settings()
    try:
        menu = load_menu(settings.menu_data_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Menu not found")

    item = get_item_by_id(menu, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item.model_dump()


@app.post("/api/menu/search")
def search_menu_endpoint(
    request: Request, payload: MenuSearchRequest
) -> MenuSearchResponse:
    settings = get_settings()
    try:
        menu = load_menu(settings.menu_data_path)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Menu not found")

    results = search_menu(
        payload.query, menu, settings.menu_index_path, top_k=payload.top_k
    )

    meta = load_rag_metadata(settings.menu_index_path)
    degraded = meta.get("degraded_mode", True)
    mode = RetrievalMode.lexical if degraded else RetrievalMode.hybrid

    confidence = results[0].score if results else 0.0

    return MenuSearchResponse(
        query=payload.query,
        results=results,
        retrieval_mode=mode,
        confidence=confidence,
        degraded_mode=degraded,
        request_id=request.state.request_id,
    )


@app.post("/api/menu/rebuild-index")
def rebuild_index() -> Any:
    settings = get_settings()
    try:
        meta = build_rag_index(
            settings.menu_data_path,
            settings.menu_index_path,
            allow_embedding_failure=True,
        )
        return {"status": "success", "metadata": meta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions", response_model=CreateSessionResponse)
def api_create_session(request: Request, payload: CreateSessionRequest) -> Any:
    return agent.start_session(
        channel=payload.channel,
        caller_id=payload.caller_id,
        request_id=request.state.request_id,
    )


@app.post("/api/turn", response_model=AgentTurnResponse)
def api_turn(request: Request, payload: AgentTurnRequest) -> Any:
    try:
        return agent.process_turn(request=payload, request_id=request.state.request_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/browser/start-call", response_model=CreateSessionResponse)
def api_browser_start_call(request: Request) -> Any:
    return agent.start_session(
        channel=Channel.browser,
        request_id=request.state.request_id,
    )


@app.post("/api/browser/voice-turn", response_model=AgentTurnResponse)
def api_browser_voice_turn(request: Request, payload: AgentTurnRequest) -> Any:
    try:
        payload.channel = Channel.browser
        return agent.process_turn(request=payload, request_id=request.state.request_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/sessions/{session_id}")
def api_get_session(session_id: str) -> Any:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()


@app.get("/api/sessions/{session_id}/order")
def api_get_order(session_id: str) -> Any:
    order = get_order(session_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order.model_dump()


@app.post("/api/sessions/{session_id}/readback")
def api_readback(session_id: str) -> Any:
    try:
        order = mark_readback_performed(session_id)
        set_dialogue_mode(session_id, DialogueMode.AWAITING_CONFIRMATION)
        return {"status": "success", "order": order.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sessions/{session_id}/confirm")
def api_confirm(session_id: str) -> Any:
    try:
        order = confirm_order(session_id)
        set_dialogue_mode(session_id, DialogueMode.CONFIRMED)
        return {"status": "success", "order": order.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sessions/{session_id}/cancel")
def api_cancel(session_id: str) -> Any:
    try:
        order = cancel_order(session_id)
        set_dialogue_mode(session_id, DialogueMode.CANCELLED)
        return {"status": "success", "order": order.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/debug/sessions/recent", response_model=RecentSessionsResponse)
def api_recent_sessions(request: Request) -> Any:
    sessions = list_recent_sessions()
    summaries = []
    for s in sessions:
        order = get_order(s.session_id)
        if order:
            summaries.append(
                RecentSessionSummary(
                    session_id=s.session_id,
                    channel=s.channel,
                    twilio_call_sid=s.twilio_call_sid,
                    order_status=order.status,
                    customer_name=order.customer_name,
                    total=order.total,
                    confirmation_id=order.confirmation_id,
                )
            )

    return RecentSessionsResponse(
        sessions=summaries, request_id=request.state.request_id
    )


@app.get("/api/debug/session/{session_id}", response_model=DebugSessionResponse)
def api_debug_session(request: Request, session_id: str) -> Any:
    session = get_session(session_id)
    order = get_order(session_id)
    if not session or not order:
        raise HTTPException(status_code=404, detail="Session/Order not found")

    return DebugSessionResponse(
        session_id=session.session_id,
        channel=session.channel,
        twilio_call_sid=session.twilio_call_sid,
        dialogue_mode=session.dialogue_mode,
        customer_name=order.customer_name,
        order_status=order.status,
        order=order,
        recent_tool_calls=[],
        recent_retrievals=[],
        degraded_llm=session.degraded_llm,
        degraded_retrieval=session.degraded_retrieval,
        request_id=request.state.request_id,
    )
