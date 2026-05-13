from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
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
from restaurant_agent.menu_ingestion import ingest_menu_text, write_canonical_menu
from restaurant_agent.menu_loader import load_menu, list_available_items, get_item_by_id
from restaurant_agent.menu_retriever import search_menu
from restaurant_agent.rag_index import build_rag_index, load_rag_metadata
from restaurant_agent.session_store import (
    find_session_by_twilio_call_sid,
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
from restaurant_agent.twilio_voice import (
    build_gather_response,
    build_goodbye_response,
    build_say_response,
    extract_speech_result,
    extract_twilio_call_sid,
    is_twilio_configured,
)

from restaurant_agent.web import render_browser_ui

app = FastAPI(title="restaurant-voice-agent")
app.add_middleware(cast(Any, RequestIDMiddleware))


def _voice_xml_response(twiml: str) -> Response:
    return Response(content=twiml, media_type="application/xml")


def _coerce_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _ingest_menu_payload(
    *, request_id: str, text: str, rebuild_index: bool
) -> Dict[str, Any]:
    settings = get_settings()
    menu = ingest_menu_text(text)
    output_path = write_canonical_menu(menu, settings.menu_data_path)

    if rebuild_index:
        build_rag_index(
            settings.menu_data_path,
            settings.menu_index_path,
            allow_embedding_failure=True,
        )

    return {
        "status": "success",
        "item_count": len(menu.items),
        "output_path": str(output_path),
        "index_rebuilt": rebuild_index,
        "request_id": request_id,
    }


def _voice_action_url(path: str) -> str:
    settings = get_settings()
    if settings.twilio_webhook_base_url:
        return urljoin(
            settings.twilio_webhook_base_url.rstrip("/") + "/", path.lstrip("/")
        )
    return path


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


@app.post("/api/menu/ingest-text")
def ingest_menu_text_endpoint(
    request: Request, payload: Dict[str, Any]
) -> Dict[str, Any]:
    text = str(payload.get("text", ""))
    rebuild_index = _coerce_bool(payload.get("rebuild_index"), default=True)

    if not text.strip():
        raise HTTPException(status_code=400, detail="Text content is required")

    try:
        return _ingest_menu_payload(
            request_id=request.state.request_id,
            text=text,
            rebuild_index=rebuild_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/menu/ingest-url")
def ingest_menu_url_endpoint(
    request: Request, payload: Dict[str, Any]
) -> Dict[str, Any]:
    url = str(payload.get("url", "")).strip()
    rebuild_index = _coerce_bool(payload.get("rebuild_index"), default=True)
    parsed = urlparse(url)

    if not url or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(
            status_code=400,
            detail="Only http and https URLs are supported for menu ingestion",
        )

    try:
        response = httpx.get(url, timeout=5.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch menu URL: {exc.__class__.__name__}",
        ) from exc

    if not response.text.strip():
        raise HTTPException(status_code=400, detail="Fetched menu content was empty")

    try:
        return _ingest_menu_payload(
            request_id=request.state.request_id,
            text=response.text,
            rebuild_index=rebuild_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/menu/ingest-file")
async def ingest_menu_file_endpoint(
    request: Request,
    file: UploadFile = File(...),
    rebuild_index: bool = Form(True),
) -> Dict[str, Any]:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    supported_extensions = {".txt", ".md", ".html", ".htm", ".csv", ".json"}

    if suffix not in supported_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file extension")
    if suffix in {".csv", ".json"}:
        raise HTTPException(
            status_code=400,
            detail=f"Structured {suffix} ingestion is not implemented in this phase",
        )

    try:
        content = (await file.read()).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="Uploaded file must be UTF-8 text"
        ) from exc
    finally:
        await file.close()

    if not content.strip():
        raise HTTPException(status_code=400, detail="Uploaded file was empty")

    try:
        return _ingest_menu_payload(
            request_id=request.state.request_id,
            text=content,
            rebuild_index=rebuild_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@app.get("/voice/config-check")
def voice_config_check() -> Dict[str, Any]:
    settings = get_settings()
    missing_fields = []
    if not settings.twilio_account_sid:
        missing_fields.append("TWILIO_ACCOUNT_SID")
    if not settings.twilio_auth_token:
        missing_fields.append("TWILIO_AUTH_TOKEN")
    if not settings.twilio_phone_number:
        missing_fields.append("TWILIO_PHONE_NUMBER")
    if not settings.twilio_webhook_base_url:
        missing_fields.append("TWILIO_WEBHOOK_BASE_URL")

    return {
        "enabled": settings.enable_twilio,
        "configured": is_twilio_configured(),
        "phone_number_configured": bool(settings.twilio_phone_number),
        "webhook_base_url_configured": bool(settings.twilio_webhook_base_url),
        "missing_fields": missing_fields,
    }


@app.post("/voice/incoming")
async def voice_incoming(request: Request) -> Response:
    form = await request.form()
    form_data = dict(form)
    call_sid = extract_twilio_call_sid(form_data)

    session = agent.start_session(
        channel=Channel.twilio,
        twilio_call_sid=call_sid,
        request_id=request.state.request_id,
    )

    action_url = _voice_action_url("/voice/turn")
    return _voice_xml_response(
        build_gather_response(session.agent_text, action_url=action_url)
    )


@app.post("/voice/turn")
async def voice_turn(request: Request) -> Response:
    form = await request.form()
    form_data = dict(form)
    call_sid = extract_twilio_call_sid(form_data)
    speech_result = extract_speech_result(form_data)

    session_state = (
        find_session_by_twilio_call_sid(call_sid) if call_sid is not None else None
    )
    if session_state is None:
        session = agent.start_session(
            channel=Channel.twilio,
            twilio_call_sid=call_sid,
            request_id=request.state.request_id,
        )
        session_id = session.session_id
    else:
        session_id = session_state.session_id

    if not speech_result:
        return _voice_xml_response(
            build_say_response("I didn't catch that. Please say that again.")
        )

    payload = AgentTurnRequest(
        session_id=session_id,
        utterance=speech_result,
        channel=Channel.twilio,
        metadata={"twilio_call_sid": call_sid} if call_sid else {},
    )

    try:
        turn_response = agent.process_turn(
            request=payload, request_id=request.state.request_id
        )
    except ValueError:
        return _voice_xml_response(
            build_say_response("Sorry, I couldn't process that. Please try again.")
        )

    if turn_response.order.status.value in {
        "confirmed",
        "cancelled",
    } or turn_response.dialogue_mode in {
        DialogueMode.CONFIRMED,
        DialogueMode.CANCELLED,
    }:
        return _voice_xml_response(build_goodbye_response(turn_response.agent_text))

    action_url = _voice_action_url("/voice/turn")
    return _voice_xml_response(
        build_gather_response(turn_response.agent_text, action_url=action_url)
    )


@app.post("/voice/status")
async def voice_status(request: Request) -> Dict[str, Any]:
    form = await request.form()
    form_data = dict(form)
    return {
        "status": "acknowledged",
        "call_sid": extract_twilio_call_sid(form_data),
        "call_status": str(form_data.get("CallStatus", "")).strip() or None,
        "request_id": request.state.request_id,
    }


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
        recent_turn_diagnostics=session.recent_turn_diagnostics,
        degraded_llm=session.degraded_llm,
        degraded_retrieval=session.degraded_retrieval,
        request_id=request.state.request_id,
    )
