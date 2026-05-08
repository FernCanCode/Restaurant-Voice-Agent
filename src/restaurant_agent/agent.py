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
from restaurant_agent.menu_retriever import (
    explicit_dietary_tag_query,
    is_explicit_taco_category_query,
)
from restaurant_agent.mcp_server import call_tool
from restaurant_agent.order_store import (
    create_order,
    get_order,
    mark_readback_performed,
    set_customer_name,
)
from restaurant_agent.pricing import format_money
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
    clear_pending_action,
    create_session,
    get_session,
    set_last_retrieved_candidates,
    set_pending_action,
    update_session,
)


_NUMBER_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
}

_BROAD_ADD_PATTERNS = {
    "give me all of it",
    "give me all of them",
    "i want all of it",
    "i want all of them",
    "i want every single item",
    "i'll take all of them",
    "add all of them",
    "add all of it",
    "one of each",
}

_PENDING_YES_PATTERNS = {
    "yes",
    "yes please",
    "yes that's right",
    "yes thats right",
    "confirm",
}

_PENDING_NO_PATTERNS = {
    "no",
    "no thanks",
    "nevermind",
    "never mind",
    "cancel",
}


def _quantity_phrase(quantity: int) -> str:
    return _NUMBER_WORDS.get(quantity, str(quantity))


def _normalize_utterance(text: str) -> str:
    return " ".join(
        text.replace("’", "'")
        .replace(",", " ")
        .replace(".", " ")
        .replace("?", " ")
        .replace("!", " ")
        .lower()
        .split()
    )


def _singularize_item_name(item_name: str, quantity: int) -> str:
    if quantity == 1 and item_name.endswith("s"):
        return item_name[:-1]
    return item_name


def _line_item_phrase(line_item: Dict[str, Any]) -> str:
    quantity = int(line_item.get("quantity", 1))
    item_name = _singularize_item_name(
        str(line_item.get("item_name", "item")), quantity
    )
    phrase = f"{_quantity_phrase(quantity)} {item_name}"

    known_modifications = line_item.get("known_modifications", [])
    special_instructions = line_item.get("special_instructions", [])

    extras = [
        str(mod.get("name", "")).strip()
        for mod in known_modifications
        if mod.get("name")
    ]
    extras.extend(
        str(inst).strip() for inst in special_instructions if str(inst).strip()
    )
    if extras:
        phrase += f" with {', '.join(extras)}"

    return phrase


def _summarize_order_for_speech(order: Any) -> str:
    if not order.items:
        return "nothing in your order yet"

    item_phrases = [
        _line_item_phrase(item.model_dump() if hasattr(item, "model_dump") else item)
        for item in order.items
    ]

    if len(item_phrases) == 1:
        return item_phrases[0]

    return ", ".join(item_phrases[:-1]) + f", and {item_phrases[-1]}"


def _deterministic_search_response(utterance: str, tool_result: Dict[str, Any]) -> str:
    results = tool_result.get("result") or []
    if is_explicit_taco_category_query(utterance):
        results = [
            result
            for result in results
            if str(result.get("category", "")).strip().lower() == "tacos"
            or "taco" in str(result.get("name", "")).strip().lower()
        ]
    names = [
        str(result.get("name", "")).strip() for result in results if result.get("name")
    ]
    if not names:
        return "I couldn't find that item on the menu."

    dietary_tag = explicit_dietary_tag_query(utterance)
    if dietary_tag:
        return (
            f"Our {dietary_tag} options are "
            + ", ".join(names[:-1])
            + (f", and {names[-1]}." if len(names) > 1 else f"{names[0]}.")
        )

    if "taco" in utterance.lower():
        return "Our taco options are " + " and ".join(names) + "."

    if len(names) == 1:
        return f"We have {names[0]}."

    return "We have " + ", ".join(names[:-1]) + f", and {names[-1]}."


def _deterministic_add_response(tool_result: Dict[str, Any]) -> str:
    order = tool_result["result"]
    added_line = order["items"][-1]
    return (
        f"Added {_line_item_phrase(added_line)}. "
        f"Your current total is {format_money(order['total'], order['currency'])}. "
        "Would you like anything else?"
    )


def _deterministic_update_response(tool_result: Dict[str, Any]) -> str:
    order = tool_result["result"]
    return (
        f"Updated your order. Your current total is "
        f"{format_money(order['total'], order['currency'])}. "
        "Would you like anything else or would you like me to review the order?"
    )


def _deterministic_remove_response(tool_result: Dict[str, Any]) -> str:
    order = tool_result["result"]
    return (
        f"Removed that item. Your current total is "
        f"{format_money(order['total'], order['currency'])}. "
        "Would you like anything else or would you like me to review the order?"
    )


def _deterministic_summary_response(order: Any) -> str:
    summary = _summarize_order_for_speech(order)
    total = format_money(order.total, order.currency)
    if not order.items:
        return "Your order is empty."
    if order.customer_name:
        return (
            f"For {order.customer_name}, I have {summary}. "
            f"Your total is {total}. Would you like me to confirm this order?"
        )
    return (
        f"I have {summary}. Your total is {total}. "
        "What name should I put the order under?"
    )


def _handle_conversation_done(request_session_id: str) -> str:
    order = get_order(request_session_id)
    if not order:
        return "I lost track of the order. What would you like to order?"

    if not order.items:
        return "I don't have anything in your order yet. What would you like to order?"

    order_summary = _summarize_order_for_speech(order)
    total = format_money(order.total, order.currency)

    if not order.customer_name:
        return (
            f"I have {order_summary}. Your current total is {total}. "
            "I can finish that. What name should I put the order under?"
        )

    if not order.readback_performed:
        mark_readback_performed(request_session_id)
        return (
            f"For {order.customer_name}, I have {order_summary}. "
            f"Your total is {total}. Would you like me to confirm this order?"
        )

    return "Would you like me to confirm this order?"


def _handle_confirm_error(request_session_id: str, error_text: str) -> str:
    order = get_order(request_session_id)
    lowered = error_text.lower()

    if "empty order" in lowered:
        return "I can confirm it once there is something in your order. What would you like to add?"

    if "without customer name" in lowered and order:
        summary = _summarize_order_for_speech(order)
        total = format_money(order.total, order.currency)
        return (
            f"I have {summary}. Your current total is {total}. "
            "I can finish that. What name should I put the order under?"
        )

    if "without readback" in lowered and order:
        mark_readback_performed(request_session_id)
        summary = _summarize_order_for_speech(order)
        total = format_money(order.total, order.currency)
        return (
            f"Before I confirm it, here is the order: {summary}. "
            f"Your total is {total}. Would you like me to confirm this order?"
        )

    if "already confirmed" in lowered:
        return "That order is already confirmed."

    if "cancelled order" in lowered:
        return "I can't confirm a cancelled order."

    return error_text or "I couldn't confirm the order."


def _is_broad_add_request(normalized: str) -> bool:
    return normalized in _BROAD_ADD_PATTERNS


def _is_pending_yes(normalized: str) -> bool:
    return normalized in _PENDING_YES_PATTERNS


def _is_pending_no(normalized: str) -> bool:
    return normalized in _PENDING_NO_PATTERNS


def _candidate_payloads(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payloads = []
    for result in results:
        item_id = str(result.get("item_id", "")).strip()
        name = str(result.get("name", "")).strip()
        if item_id and name:
            payloads.append({"item_id": item_id, "name": name})
    return payloads


def _format_candidate_names(candidates: list[dict[str, Any]]) -> str:
    names = [
        str(candidate["name"])
        for candidate in candidates
        if candidate.get("name") is not None
    ]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _handle_broad_add_request(session_id: str) -> str:
    session = get_session(session_id)
    if not session or not session.last_retrieved_candidates:
        return "Which items would you like me to add?"

    names = _format_candidate_names(session.last_retrieved_candidates)
    question = "Just to confirm, do you want one of each of these items: " f"{names}?"
    set_pending_action(session_id, "confirm_add_all", question)
    return question


def _handle_pending_add_all(
    request_session_id: str, request_id: Optional[str]
) -> tuple[str, list[ToolCallSummary]]:
    session = get_session(request_session_id)
    if not session or not session.last_retrieved_candidates:
        clear_pending_action(request_session_id)
        return ("Which items would you like me to add?", [])

    tool_calls: list[ToolCallSummary] = []
    latest_order = None

    for candidate in session.last_retrieved_candidates:
        res = call_tool(
            tool_name="add_order_item",
            arguments={
                "session_id": request_session_id,
                "item_id": candidate["item_id"],
                "quantity": 1,
            },
            request_id=request_id,
        )
        status = ToolStatus.success if res["status"] == "success" else ToolStatus.error
        tool_calls.append(
            ToolCallSummary(
                tool_name="add_order_item",
                status=status,
                summary=res["error"] if res["error"] else f"Added {candidate['name']}",
            )
        )
        if status == ToolStatus.error:
            clear_pending_action(request_session_id)
            return (res["error"] or "I couldn't add those items.", tool_calls)
        latest_order = res["result"]

    clear_pending_action(request_session_id)
    if not latest_order:
        return ("I couldn't add those items.", tool_calls)

    names = _format_candidate_names(session.last_retrieved_candidates)
    total = format_money(latest_order["total"], latest_order["currency"])
    return (
        f"Added one of each: {names}. Your current total is {total}. "
        "Would you like anything else?",
        tool_calls,
    )


def _clear_list_context_after_decline(session_id: str) -> str:
    clear_pending_action(session_id)
    return "Okay, I won't add those items. What would you like instead?"


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
    session.last_user_utterance = request.utterance
    update_session(session)

    order = get_order(request.session_id)
    # Get last known line item ID from request metadata
    line_item_id = request.metadata.get("line_item_id")
    normalized_utterance = _normalize_utterance(request.utterance)

    session_context: Dict[str, Any] = {
        "session_id": request.session_id,
        "dialogue_mode": session.dialogue_mode.value,
        "line_item_id": line_item_id,
        "pending_action": session.pending_action,
        "last_retrieved_candidates": session.last_retrieved_candidates,
    }

    degraded = False
    proposal: Any
    tool_calls: list[ToolCallSummary] = []
    response_text = ""
    intent_override: Optional[str] = None

    if session.pending_action == "confirm_add_all":
        if _is_pending_yes(normalized_utterance):
            response_text, tool_calls = _handle_pending_add_all(
                request.session_id, request_id
            )
            intent_override = "confirm_add_all"
        elif _is_pending_no(normalized_utterance):
            response_text = _clear_list_context_after_decline(request.session_id)
            intent_override = "confirm_add_all"
        else:
            response_text = session.pending_question or (
                "Please say yes to add one of each item I just listed, or no to keep the order as it is."
            )
            intent_override = "confirm_add_all"
    elif _is_broad_add_request(normalized_utterance):
        response_text = _handle_broad_add_request(request.session_id)
        intent_override = "broad_add_request"

    if intent_override is None:
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

        if proposal.intent == "conversation_done":
            response_text = _handle_conversation_done(request.session_id)

        elif proposal.intent == "broad_add_request":
            response_text = _handle_broad_add_request(request.session_id)

        elif proposal.intent == "set_customer_name":
            name = proposal.arguments.get("customer_name")
            if name:
                set_customer_name(request.session_id, name)
                response_text = proposal.response_text or (
                    f"Got it, the order is under {name}. "
                    "When you're ready, I can review the order and confirm it."
                )
            else:
                response_text = "I didn't quite catch your name."

        elif not getattr(proposal, "safe_to_execute", True):
            response_text = (
                proposal.clarification_question
                or proposal.response_text
                or "I am not sure what to do."
            )

        elif proposal.tool_name:
            res = call_tool(
                tool_name=proposal.tool_name,
                arguments=proposal.arguments,
                request_id=request_id,
            )
            status = (
                ToolStatus.success if res["status"] == "success" else ToolStatus.error
            )
            tool_calls.append(
                ToolCallSummary(
                    tool_name=proposal.tool_name,
                    status=status,
                    summary=res["error"] if res["error"] else "Success",
                )
            )

            if status == ToolStatus.error:
                if proposal.tool_name == "confirm_order":
                    response_text = _handle_confirm_error(
                        request.session_id, res["error"] or ""
                    )
                elif "not found" in (res["error"] or "").lower():
                    response_text = "I couldn't find that item on the menu."
                else:
                    response_text = res["error"] or "There was an error."
            else:
                if proposal.tool_name == "get_order_summary":
                    mark_readback_performed(request.session_id)
                elif proposal.tool_name == "search_menu":
                    set_last_retrieved_candidates(
                        request.session_id, _candidate_payloads(res.get("result", []))
                    )

                should_use_deterministic_search = (
                    proposal.tool_name == "search_menu"
                    and (
                        is_explicit_taco_category_query(request.utterance)
                        or explicit_dietary_tag_query(request.utterance) is not None
                    )
                )
                try:
                    if should_use_deterministic_search:
                        raise LLMUnavailableError(
                            "Use deterministic menu-category response"
                        )
                    response_text = generate_response_text(
                        utterance=request.utterance,
                        tool_result=res,
                        session_context=session_context,
                        request_id=request_id,
                    )
                except LLMUnavailableError:
                    if proposal.tool_name == "add_order_item":
                        response_text = _deterministic_add_response(res)
                    elif proposal.tool_name == "update_order_item":
                        response_text = _deterministic_update_response(res)
                    elif proposal.tool_name == "remove_order_item":
                        response_text = _deterministic_remove_response(res)
                    elif proposal.tool_name == "search_menu":
                        response_text = _deterministic_search_response(
                            request.utterance, res
                        )
                    elif proposal.tool_name == "check_dietary_info":
                        response_text = res["result"].get(
                            "answer", "Here is the dietary info."
                        )
                    elif proposal.tool_name in ["compute_total", "get_order_summary"]:
                        if proposal.tool_name == "compute_total":
                            total = res["result"].get("formatted_total", "")
                            response_text = (
                                f"Your current total is {total}. "
                                "Would you like anything else or would you like me to review the order?"
                            )
                        else:
                            response_text = _deterministic_summary_response(order)
                    elif proposal.tool_name == "confirm_order":
                        confirmation_id = res["result"].get("confirmation_id", "")
                        response_text = (
                            "Your order is confirmed. "
                            f"Your confirmation ID is {confirmation_id}."
                        )
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

    session.last_agent_response = response_text
    session.last_intent = intent_override or getattr(proposal, "intent", None)
    update_session(session)

    return AgentTurnResponse(
        session_id=session.session_id,
        dialogue_mode=session.dialogue_mode,
        intent=intent_override or getattr(proposal, "intent", None),
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
