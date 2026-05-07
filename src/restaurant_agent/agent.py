"""Agent orchestrator for the restaurant voice ordering assistant.

This module provides the shared backend turn-processing flow used by both
browser voice and Twilio phone routes.
"""

from typing import Any, Dict, Optional

from restaurant_agent.llm_client import (
    LLMUnavailableError,
    generate_response_text,
    propose_tool_route,
)
from restaurant_agent.fallback_parser import parse_fallback_intent
from restaurant_agent.mcp_server import call_tool
from restaurant_agent.order_store import (
    create_order,
    get_order,
    set_customer_name,
)
from restaurant_agent.schemas import (
    AgentTurnRequest,
    AgentTurnResponse,
    Channel,
    CreateSessionResponse,
    RetrievalMode,
    RetrievalSummary,
    ToolCallSummary,
    ToolStatus,
)
from restaurant_agent.session_store import (
    append_turn,
    create_session,
    get_session,
    update_session,
)


def start_session(
    channel: Channel = Channel.browser,
    caller_id: Optional[str] = None,
    twilio_call_sid: Optional[str] = None,
    request_id: Optional[str] = None,
) -> CreateSessionResponse:
    """Create a new dialogue session and order, returning a greeting."""
    session = create_session(
        channel=channel, caller_id=caller_id, twilio_call_sid=twilio_call_sid
    )
    order = create_order(session.session_id)

    greeting_text = (
        "Welcome to the restaurant voice ordering assistant. "
        "I can answer menu questions and help take your order. "
        "What would you like today?"
    )

    append_turn(
        session_id=session.session_id,
        role="agent",
        content=greeting_text,
        request_id=request_id,
    )

    return CreateSessionResponse(
        session_id=session.session_id,
        dialogue_mode=session.dialogue_mode,
        agent_text=greeting_text,
        order=order,
        next_action="await_user",
        request_id=request_id or "",
    )


def process_turn(
    request: AgentTurnRequest, request_id: Optional[str] = None
) -> AgentTurnResponse:
    """Process a single conversational turn."""
    session = get_session(request.session_id)
    if not session:
        raise ValueError("Session not found")

    append_turn(
        session_id=request.session_id,
        role="user",
        content=request.utterance,
        request_id=request_id,
    )

    order = get_order(request.session_id)
    # Get last known line item ID from request metadata
    line_item_id = request.metadata.get("line_item_id")

    session_context: Dict[str, Any] = {
        "session_id": request.session_id,
        "dialogue_mode": session.dialogue_mode.value,
        "line_item_id": line_item_id,
    }

    degraded = False
    proposal: Any
    try:
        proposal = propose_tool_route(
            utterance=request.utterance,
            session_context=session_context,
            request_id=request_id,
        )
    except LLMUnavailableError:
        proposal = parse_fallback_intent(
            utterance=request.utterance, session_context=session_context
        )
        degraded = True
        session.degraded_llm = True
        update_session(session)

    tool_calls = []
    response_text = ""

    if proposal.intent == "set_customer_name":
        # Deterministic special case for customer name
        name = proposal.arguments.get("customer_name")
        if name:
            set_customer_name(request.session_id, name)
            response_text = (
                proposal.response_text or f"Got it, the order is under {name}."
            )
        else:
            response_text = "I didn't quite catch your name."

    elif not getattr(proposal, "safe_to_execute", True):
        # Refusal or clarification question
        response_text = (
            proposal.clarification_question
            or proposal.response_text
            or "I am not sure what to do."
        )

    elif proposal.tool_name:
        # Call the requested MCP tool
        res = call_tool(
            tool_name=proposal.tool_name,
            arguments=proposal.arguments,
            request_id=request_id,
        )
        status = ToolStatus.success if res["status"] == "success" else ToolStatus.error
        tool_calls.append(
            ToolCallSummary(
                tool_name=proposal.tool_name,
                status=status,
                summary=res["error"] if res["error"] else "Success",
            )
        )

        if status == ToolStatus.error:
            # Fallback parser may propose tools that error (e.g. invalid item)
            # which we map cleanly back to text here
            if "not found" in (res["error"] or "").lower():
                response_text = "I couldn't find that item on the menu."
            else:
                response_text = res["error"] or "There was an error."
        else:
            if proposal.tool_name == "get_order_summary":
                from restaurant_agent.order_store import mark_readback_performed

                mark_readback_performed(request.session_id)

            try:
                response_text = generate_response_text(
                    utterance=request.utterance,
                    tool_result=res,
                    session_context=session_context,
                    request_id=request_id,
                )
            except LLMUnavailableError:
                # Deterministic formatting
                if proposal.tool_name == "add_order_item":
                    response_text = "Item added to your order."
                elif proposal.tool_name == "remove_order_item":
                    response_text = "Item removed from your order."
                elif proposal.tool_name == "search_menu":
                    results = res["result"] if res.get("result") else []
                    names = [r.get("name", "") for r in results]
                    response_text = "We have " + ", ".join(names)
                elif proposal.tool_name == "check_dietary_info":
                    response_text = res["result"].get(
                        "answer", "Here is the dietary info."
                    )
                elif proposal.tool_name in ["compute_total", "get_order_summary"]:
                    summary = res["result"].get("summary", "")
                    total = res["result"].get("formatted_total", "")
                    response_text = summary if summary else f"Your total is {total}."
                elif proposal.tool_name == "confirm_order":
                    response_text = "Your order has been confirmed!"
                elif proposal.tool_name == "cancel_order":
                    response_text = "Your order has been cancelled."
                else:
                    response_text = "Action completed successfully."
    else:
        response_text = proposal.response_text or "I am unable to process that."

    append_turn(
        session_id=request.session_id,
        role="agent",
        content=response_text,
        request_id=request_id,
    )

    # Note: `get_order_summary` inherently performs readback through the logic
    # if it's explicitly asked for, but to be sure we're marking it in the
    # system we check the order here to ensure it's up-to-date and if readback
    # is required we can check the tool name
    order = get_order(request.session_id)
    session = get_session(request.session_id)

    if not order or not session:
        raise ValueError("Session or Order disappeared during turn processing")

    return AgentTurnResponse(
        session_id=session.session_id,
        dialogue_mode=session.dialogue_mode,
        intent=proposal.intent,
        agent_text=response_text,
        speak=True,
        order=order,
        tool_calls=tool_calls,
        retrieval=RetrievalSummary(
            used=False, mode=RetrievalMode.degraded, confidence=0.0
        ),
        requires_user_response=True,
        next_action="await_user",
        degraded_mode=degraded,
        request_id=request_id or "",
    )
