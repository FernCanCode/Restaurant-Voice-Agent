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
from restaurant_agent.fallback_parser import (
    ParsedFallbackIntent,
    match_menu_item_id,
    parse_fallback_intent,
)
from restaurant_agent.config import get_settings
from restaurant_agent.menu_loader import get_item_by_id, load_menu
from restaurant_agent.menu_retriever import (
    explicit_collection_query,
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
    append_turn_diagnostic,
    append_turn,
    clear_pending_action,
    create_session,
    get_session,
    set_last_mentioned_item,
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
    "give me one of each of those",
    "give me one of each",
    "one of each of those",
    "one of each of them",
    "all of them",
    "all of those",
    "all of that",
    "give me all of it",
    "give me all of that",
    "give me all of those",
    "give me all of them",
    "i want all of it",
    "i want all of that",
    "i want all of those",
    "i want all of them",
    "i want every single item",
    "i'll take all of them",
    "i'll take all of that",
    "add all of them",
    "add all of it",
    "add all of that",
    "one of each",
}

_PENDING_YES_PATTERNS = {
    "yes",
    "yes please",
    "yes that's right",
    "yes thats right",
    "confirm",
    "confirm order",
    "confirm my order",
    "yes confirm",
    "yes, confirm",
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
    normalized = text.replace("’", "'").replace("‘", "'").replace("`", "'").lower()
    normalized = normalized.replace(",", " ").replace(".", " ").replace("?", " ")
    normalized = normalized.replace("!", " ").replace(";", " ").replace(":", " ")
    normalized = " ".join(normalized.split())
    normalized = normalized.replace("i ll", "i'll")
    if normalized.startswith("ill "):
        normalized = "i'll " + normalized[4:]
    if normalized.endswith(" please"):
        normalized = normalized[: -len(" please")]
    return normalized


def _singularize_item_name(item_name: str, quantity: int) -> str:
    if quantity == 1 and item_name.endswith("s"):
        return item_name[:-1]
    return item_name


def _display_item_name(item_name: str, quantity: int) -> str:
    normalized = item_name.strip()
    if quantity == 1:
        return _singularize_item_name(normalized, quantity)
    if normalized.endswith("s"):
        return normalized
    return f"{normalized}s"


def _line_item_phrase(line_item: Dict[str, Any]) -> str:
    quantity = int(line_item.get("quantity", 1))
    item_name = _display_item_name(str(line_item.get("item_name", "item")), quantity)
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

    grouped_items: Dict[
        tuple[str, tuple[str, ...], tuple[str, ...]], Dict[str, Any]
    ] = {}
    for item in order.items:
        item_data = item.model_dump() if hasattr(item, "model_dump") else item
        mod_names = tuple(
            str(mod.get("name", "")).strip()
            for mod in item_data.get("known_modifications", [])
            if str(mod.get("name", "")).strip()
        )
        instructions = tuple(
            str(inst).strip()
            for inst in item_data.get("special_instructions", [])
            if str(inst).strip()
        )
        key = (str(item_data.get("item_name", "item")), mod_names, instructions)
        if key not in grouped_items:
            grouped_items[key] = dict(item_data)
        else:
            grouped_items[key]["quantity"] = int(
                grouped_items[key].get("quantity", 1)
            ) + int(item_data.get("quantity", 1))

    item_phrases = [
        _line_item_phrase(item_data) for item_data in grouped_items.values()
    ]

    if len(item_phrases) == 1:
        return item_phrases[0]

    return ", ".join(item_phrases[:-1]) + f", and {item_phrases[-1]}"


def _deterministic_search_response(utterance: str, tool_result: Dict[str, Any]) -> str:
    results = tool_result.get("result") or []
    collection_query = explicit_collection_query(utterance)
    if collection_query == "tacos":
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

    if collection_query in {"vegetarian", "vegan"}:
        return (
            f"Our {collection_query} options are "
            + ", ".join(names[:-1])
            + (f", and {names[-1]}." if len(names) > 1 else f"{names[0]}.")
        )

    if collection_query == "tacos":
        return "Our taco options are " + " and ".join(names) + "."
    if collection_query == "drinks":
        return "Our drink options are " + " and ".join(names) + "."
    if collection_query == "meat":
        return "Our meat options are " + " and ".join(names) + "."
    if collection_query == "sides":
        return "Our side options are " + " and ".join(names) + "."

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
        set_pending_action(request_session_id, "collect_customer_name")
        return (
            f"I have {order_summary}. Your current total is {total}. "
            "I can finish that. What name should I put the order under?"
        )

    if not order.readback_performed:
        clear_pending_action(request_session_id)
        mark_readback_performed(request_session_id)
        return (
            f"For {order.customer_name}, I have {order_summary}. "
            f"Your total is {total}. Would you like me to confirm this order?"
        )

    clear_pending_action(request_session_id)
    return "Would you like me to confirm this order?"


def _handle_confirm_error(request_session_id: str, error_text: str) -> str:
    order = get_order(request_session_id)
    lowered = error_text.lower()

    if "empty order" in lowered:
        return "I can confirm it once there is something in your order. What would you like to add?"

    if "without customer name" in lowered and order:
        set_pending_action(request_session_id, "collect_customer_name")
        summary = _summarize_order_for_speech(order)
        total = format_money(order.total, order.currency)
        return (
            f"I have {summary}. Your current total is {total}. "
            "I can finish that. What name should I put the order under?"
        )

    if "without readback" in lowered and order:
        clear_pending_action(request_session_id)
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


def _handle_set_customer_name(session_id: str, proposal: ParsedFallbackIntent) -> str:
    name = proposal.arguments.get("customer_name")
    if not name:
        return "I didn't quite catch your name."

    session = get_session(session_id)
    order = get_order(session_id)
    was_collecting_name = bool(
        session and session.pending_action == "collect_customer_name"
    )
    set_customer_name(session_id, str(name))
    clear_pending_action(session_id)

    if order and order.items and was_collecting_name:
        refreshed_order = get_order(session_id)
        if refreshed_order and not refreshed_order.readback_performed:
            refreshed_order = mark_readback_performed(session_id)
            summary = _summarize_order_for_speech(refreshed_order)
            total = format_money(refreshed_order.total, refreshed_order.currency)
            return (
                f"Got it, the order is under {name}. "
                f"For {name}, I have {summary}. Your total is {total}. "
                "Would you like me to confirm this order?"
            )

        if refreshed_order:
            return (
                f"Got it, the order is under {name}. "
                "Would you like me to confirm this order?"
            )

    return proposal.response_text or (
        f"Got it, the order is under {name}. "
        "When you're ready, I can review the order and confirm it."
    )


def _handle_price_lookup(proposal: ParsedFallbackIntent) -> str:
    item_id = str(proposal.arguments.get("item_id", "")).strip()
    if not item_id:
        return "Which item would you like me to price?"

    settings = get_settings()
    menu = load_menu(settings.menu_data_path)
    item = get_item_by_id(menu, item_id)
    if not item:
        return "I couldn't find that item on the menu."

    return f"{item.name} is {format_money(item.base_price, menu.restaurant.currency)}."


def _match_order_line_items_by_item_id(
    session_id: str, item_id: str
) -> list[dict[str, Any]]:
    order = get_order(session_id)
    if not order:
        return []

    matches: list[dict[str, Any]] = []
    for item in order.items:
        item_data = item.model_dump()
        if str(item_data.get("item_id", "")).strip() == item_id:
            matches.append(item_data)
    return matches


def _handle_remove_by_name(
    session_id: str,
    proposal: ParsedFallbackIntent,
    request_id: Optional[str],
) -> tuple[str, list[ToolCallSummary]]:
    item_id = str(proposal.arguments.get("item_id", "")).strip()
    if not item_id:
        return ("Which item would you like to remove?", [])

    matches = _match_order_line_items_by_item_id(session_id, item_id)
    if not matches:
        settings = get_settings()
        menu = load_menu(settings.menu_data_path)
        menu_item = get_item_by_id(menu, item_id)
        item_name = menu_item.name if menu_item else "that item"
        return (f"{item_name} is not currently in your order.", [])

    if len(matches) > 1:
        question = "I found more than one matching item in your order."
        return (
            _set_pending_remove_clarification(session_id, matches, question),
            [],
        )

    res = call_tool(
        tool_name="remove_order_item",
        arguments={
            "session_id": session_id,
            "line_item_id": matches[0]["line_item_id"],
        },
        request_id=request_id,
    )
    status = ToolStatus.success if res["status"] == "success" else ToolStatus.error
    tool_calls = [
        ToolCallSummary(
            tool_name="remove_order_item",
            status=status,
            summary=res["error"] if res["error"] else "Removed matching item",
        )
    ]
    if status == ToolStatus.error:
        return (res["error"] or "I couldn't remove that item.", tool_calls)

    return (_deterministic_remove_response(res), tool_calls)


def _maybe_track_last_mentioned_item(
    session_id: str,
    proposal: Optional[ParsedFallbackIntent],
    response_text: str,
    tool_result: Optional[Dict[str, Any]] = None,
) -> None:
    if proposal is None:
        return

    if proposal.intent == "price_lookup":
        item_id = str(proposal.arguments.get("item_id", "")).strip() or None
        set_last_mentioned_item(session_id, item_id)
        return

    if proposal.tool_name == "search_menu" and tool_result is not None:
        results = tool_result.get("result") or []
        if len(results) == 1 and results[0].get("item_id"):
            set_last_mentioned_item(session_id, str(results[0]["item_id"]))
        return

    if proposal.tool_name in {"add_order_item", "add_multiple_items"}:
        return

    if response_text:
        return


def _deterministic_pre_route(
    utterance: str,
    session_context: Dict[str, Any],
) -> Optional[ParsedFallbackIntent]:
    proposal = parse_fallback_intent(
        utterance=utterance, session_context=session_context
    )

    if proposal.intent in {
        "conversation_done",
        "confirm_order",
        "broad_add_request",
        "price_lookup",
        "set_customer_name",
        "compute_total",
        "get_order_summary",
        "remove_order_item_by_name",
    }:
        return proposal

    if (
        proposal.intent == "search_menu"
        and explicit_collection_query(utterance) is not None
    ):
        return proposal

    if proposal.intent in {"add_order_item", "add_multiple_items"} and getattr(
        proposal, "safe_to_execute", False
    ):
        return proposal

    return None


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


def _handle_multiple_add_request(
    proposal: ParsedFallbackIntent,
    request_id: Optional[str],
) -> tuple[str, list[ToolCallSummary]]:
    tool_calls: list[ToolCallSummary] = []
    latest_order = None
    added_names: list[str] = []

    for item_args in proposal.arguments.get("items", []):
        res = call_tool(
            tool_name="add_order_item",
            arguments=item_args,
            request_id=request_id,
        )
        status = ToolStatus.success if res["status"] == "success" else ToolStatus.error
        tool_calls.append(
            ToolCallSummary(
                tool_name="add_order_item",
                status=status,
                summary=(
                    res["error"] if res["error"] else f"Added {item_args['item_id']}"
                ),
            )
        )
        if status == ToolStatus.error:
            return (res["error"] or "I couldn't add those items.", tool_calls)
        latest_order = res["result"]
        added_names.append(latest_order["items"][-1]["item_name"])

    if not latest_order:
        return ("I couldn't add those items.", tool_calls)

    total = format_money(latest_order["total"], latest_order["currency"])
    item_phrase = ", ".join(added_names[:-1]) + (
        f", and {added_names[-1]}" if len(added_names) > 1 else added_names[0]
    )
    return (
        f"Added {item_phrase}. Your current total is {total}. Would you like anything else?",
        tool_calls,
    )


def _clear_list_context_after_decline(session_id: str) -> str:
    clear_pending_action(session_id)
    return "Okay, I won't add those items. What would you like instead?"


def _normalize_candidate_tokens(text: str) -> set[str]:
    normalized = _normalize_utterance(text)
    tokens = {
        token.rstrip("s")
        for token in normalized.split()
        if token
        not in {
            "the",
            "a",
            "an",
            "my",
            "item",
            "items",
            "line",
            "remove",
            "delete",
            "drop",
            "cancel",
        }
    }
    return {token for token in tokens if token}


def _line_item_to_pending_candidate(item: Any) -> Dict[str, Any]:
    item_data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
    return {
        "line_item_id": item_data["line_item_id"],
        "item_id": item_data["item_id"],
        "item_name": item_data["item_name"],
        "quantity": item_data["quantity"],
        "special_instructions": item_data.get("special_instructions", []),
        "known_modifications": item_data.get("known_modifications", []),
    }


def _format_remove_options(candidates: list[dict[str, Any]]) -> str:
    phrases = [_line_item_phrase(candidate) for candidate in candidates]
    if not phrases:
        return ""
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + f", and {phrases[-1]}"


def _find_remove_candidates(session_id: str, utterance: str) -> list[dict[str, Any]]:
    order = get_order(session_id)
    if not order or not order.items:
        return []

    candidate_item_id = match_menu_item_id(utterance)
    if candidate_item_id:
        return [
            _line_item_to_pending_candidate(item)
            for item in order.items
            if item.item_id == candidate_item_id
        ]

    normalized = _normalize_utterance(utterance)
    stripped = normalized
    for prefix in ("remove", "delete", "drop", "cancel"):
        if stripped.startswith(prefix + " "):
            stripped = stripped[len(prefix) :].strip()
            break
    query_tokens = _normalize_candidate_tokens(stripped)
    if not query_tokens:
        return []

    matches: list[dict[str, Any]] = []
    for item in order.items:
        item_tokens = _normalize_candidate_tokens(item.item_name)
        if query_tokens & item_tokens:
            matches.append(_line_item_to_pending_candidate(item))
    return matches


def _set_pending_remove_clarification(
    session_id: str, candidates: list[dict[str, Any]], question: str
) -> str:
    set_pending_action(
        session_id,
        "clarify_remove_item",
        question,
        pending_context={"candidates": candidates},
    )
    if candidates:
        return f"{question} I found {_format_remove_options(candidates)} in your order."
    return question


def _set_pending_special_instruction_confirmation(
    session_id: str, proposal: ParsedFallbackIntent
) -> str:
    question = (
        proposal.clarification_question or "Should I add that as a special instruction?"
    )
    set_pending_action(
        session_id,
        "confirm_add_special_instruction",
        question,
        pending_context={
            "tool_name": "add_order_item",
            "arguments": dict(proposal.arguments),
        },
    )
    return question


def _handle_pending_special_instruction(
    session_id: str, normalized_utterance: str, request_id: Optional[str]
) -> tuple[str, list[ToolCallSummary], Optional[str]]:
    session = get_session(session_id)
    if not session:
        return ("I lost track of the order. What would you like to add?", [], None)

    pending_args = dict(session.pending_context.get("arguments") or {})
    if not pending_args:
        clear_pending_action(session_id)
        return ("I lost track of that request. What would you like to add?", [], None)

    if _is_pending_no(normalized_utterance):
        clear_pending_action(session_id)
        return ("Okay, I won't add that item. What would you like instead?", [], None)

    if not _is_pending_yes(normalized_utterance):
        return (
            session.pending_question
            or "Please say yes to add it as a special instruction, or no to skip it.",
            [],
            None,
        )

    pending_args.setdefault("known_modification_names", [])
    pending_args.setdefault("special_instructions", [])
    res = call_tool(
        tool_name="add_order_item",
        arguments=pending_args,
        request_id=request_id,
    )
    status = ToolStatus.success if res["status"] == "success" else ToolStatus.error
    tool_calls = [
        ToolCallSummary(
            tool_name="add_order_item",
            status=status,
            summary=(
                res["error"]
                if res["error"]
                else "Added pending special-instruction item"
            ),
        )
    ]
    clear_pending_action(session_id)
    if status == ToolStatus.error:
        return (res["error"] or "I couldn't add that item.", tool_calls, None)

    latest_order = res["result"]
    added_line = latest_order["items"][-1]
    total = format_money(latest_order["total"], latest_order["currency"])
    return (
        f"Added {_line_item_phrase(added_line)} as a special instruction. "
        f"Your current total is {total}. Would you like anything else?",
        tool_calls,
        "add_order_item",
    )


def _resolve_pending_remove_clarification(
    session_id: str, utterance: str, request_id: Optional[str]
) -> tuple[str, list[ToolCallSummary], Optional[str]]:
    session = get_session(session_id)
    if not session:
        return ("I lost track of the order. What would you like to remove?", [], None)

    candidates = list(session.pending_context.get("candidates") or [])
    if not candidates:
        clear_pending_action(session_id)
        return (
            "I lost track of that removal. What would you like to remove?",
            [],
            None,
        )

    if _is_pending_no(_normalize_utterance(utterance)):
        clear_pending_action(session_id)
        return ("Okay, I won't remove anything.", [], None)

    matched_item_id = match_menu_item_id(utterance)
    matching_candidates = candidates
    if matched_item_id:
        matching_candidates = [
            candidate
            for candidate in candidates
            if str(candidate.get("item_id", "")).strip() == matched_item_id
        ]
    else:
        reply_tokens = _normalize_candidate_tokens(utterance)
        filtered = []
        for candidate in candidates:
            candidate_tokens = _normalize_candidate_tokens(
                str(candidate.get("item_name", ""))
            )
            if reply_tokens and reply_tokens <= candidate_tokens:
                filtered.append(candidate)
        if filtered:
            matching_candidates = filtered

    if not matching_candidates:
        options = _format_remove_options(candidates)
        return (
            f"That isn't one of the removal options I listed. "
            f"Please choose from {options}.",
            [],
            None,
        )

    if len(matching_candidates) > 1:
        options = _format_remove_options(matching_candidates)
        return (
            "I still found more than one matching item to remove: "
            f"{options}. Which one would you like me to remove?",
            [],
            None,
        )

    res = call_tool(
        tool_name="remove_order_item",
        arguments={
            "session_id": session_id,
            "line_item_id": matching_candidates[0]["line_item_id"],
        },
        request_id=request_id,
    )
    status = ToolStatus.success if res["status"] == "success" else ToolStatus.error
    tool_calls = [
        ToolCallSummary(
            tool_name="remove_order_item",
            status=status,
            summary=(
                res["error"] if res["error"] else "Removed clarified matching item"
            ),
        )
    ]
    clear_pending_action(session_id)
    if status == ToolStatus.error:
        return (res["error"] or "I couldn't remove that item.", tool_calls, None)

    return (_deterministic_remove_response(res), tool_calls, "remove_order_item")


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
        "pending_context": session.pending_context,
        "last_retrieved_candidates": session.last_retrieved_candidates,
        "last_mentioned_item_id": session.last_mentioned_item_id,
        "last_intent": session.last_intent,
        "last_agent_response": session.last_agent_response,
    }

    degraded = False
    proposal: Any = None
    tool_calls: list[ToolCallSummary] = []
    response_text = ""
    intent_override: Optional[str] = None
    preserve_pending_add_all = False
    routing_source = "deterministic"
    selected_tool_name: Optional[str] = None
    deterministic_intent: Optional[str] = None

    if session.pending_action == "confirm_add_special_instruction":
        response_text, tool_calls, selected_tool_name = (
            _handle_pending_special_instruction(
                request.session_id, normalized_utterance, request_id
            )
        )
        intent_override = "confirm_add_special_instruction"
    elif session.pending_action == "clarify_remove_item":
        response_text, tool_calls, selected_tool_name = (
            _resolve_pending_remove_clarification(
                request.session_id, request.utterance, request_id
            )
        )
        intent_override = "clarify_remove_item"
    elif session.pending_action == "confirm_add_all":
        if _is_pending_yes(normalized_utterance):
            response_text, tool_calls = _handle_pending_add_all(
                request.session_id, request_id
            )
            intent_override = "confirm_add_all"
        elif _is_pending_no(normalized_utterance):
            response_text = _clear_list_context_after_decline(request.session_id)
            intent_override = "confirm_add_all"
        else:
            pending_proposal = _deterministic_pre_route(
                request.utterance, session_context
            )
            if pending_proposal is not None:
                deterministic_intent = pending_proposal.intent
                preserve_pending_add_all = pending_proposal.intent in {
                    "price_lookup",
                    "search_menu",
                    "compute_total",
                    "get_order_summary",
                }
                if not preserve_pending_add_all:
                    clear_pending_action(request.session_id)
                    session = get_session(request.session_id)
                    if session:
                        session_context["pending_action"] = session.pending_action
                proposal = pending_proposal
            else:
                response_text = session.pending_question or (
                    "Please say yes to add one of each item I just listed, or no to keep the order as it is."
                )
                intent_override = "confirm_add_all"
    if intent_override is None:
        deterministic_proposal = proposal or _deterministic_pre_route(
            request.utterance, session_context
        )
        if deterministic_proposal is not None:
            deterministic_intent = deterministic_proposal.intent
            if deterministic_proposal.intent == "conversation_done":
                response_text = _handle_conversation_done(request.session_id)
                intent_override = "conversation_done"
            elif deterministic_proposal.intent == "broad_add_request":
                response_text = _handle_broad_add_request(request.session_id)
                intent_override = "broad_add_request"
            elif deterministic_proposal.intent == "set_customer_name":
                response_text = _handle_set_customer_name(
                    request.session_id, deterministic_proposal
                )
                intent_override = "set_customer_name"
            elif deterministic_proposal.intent == "price_lookup":
                response_text = _handle_price_lookup(deterministic_proposal)
                _maybe_track_last_mentioned_item(
                    request.session_id, deterministic_proposal, response_text
                )
                intent_override = "price_lookup"
            elif deterministic_proposal.intent == "remove_order_item_by_name":
                response_text, tool_calls = _handle_remove_by_name(
                    request.session_id, deterministic_proposal, request_id
                )
                if tool_calls:
                    selected_tool_name = "remove_order_item"
                intent_override = "remove_order_item_by_name"
            else:
                proposal = deterministic_proposal

    if not response_text and intent_override is None:
        if proposal is None:
            try:
                routing_source = "anthropic"
                proposal = propose_tool_route(
                    utterance=request.utterance,
                    session_context=session_context,
                    request_id=request_id,
                )
            except LLMUnavailableError:
                routing_source = "fallback"
                proposal = parse_fallback_intent(
                    utterance=request.utterance, session_context=session_context
                )
                degraded = True
                if session is not None:
                    session.degraded_llm = True
                    update_session(session)

        if proposal.intent == "conversation_done":
            response_text = _handle_conversation_done(request.session_id)

        elif proposal.intent == "broad_add_request":
            response_text = _handle_broad_add_request(request.session_id)

        elif proposal.intent == "set_customer_name":
            response_text = _handle_set_customer_name(request.session_id, proposal)

        elif proposal.intent == "price_lookup":
            response_text = _handle_price_lookup(proposal)
            _maybe_track_last_mentioned_item(
                request.session_id, proposal, response_text
            )

        elif proposal.intent == "remove_order_item_by_name":
            response_text, tool_calls = _handle_remove_by_name(
                request.session_id, proposal, request_id
            )
            if tool_calls:
                selected_tool_name = "remove_order_item"

        elif proposal.intent == "add_multiple_items":
            response_text, tool_calls = _handle_multiple_add_request(
                proposal, request_id
            )

        elif not getattr(proposal, "safe_to_execute", True):
            if proposal.tool_name == "add_order_item" and proposal.arguments.get(
                "special_instructions"
            ):
                response_text = _set_pending_special_instruction_confirmation(
                    request.session_id, proposal
                )
            elif proposal.intent == "remove_order_item":
                candidates = _find_remove_candidates(
                    request.session_id, request.utterance
                )
                response_text = _set_pending_remove_clarification(
                    request.session_id,
                    candidates,
                    proposal.clarification_question
                    or "Which item would you like to remove?",
                )
            else:
                response_text = (
                    proposal.clarification_question
                    or proposal.response_text
                    or "I am not sure what to do."
                )

        elif proposal.tool_name:
            selected_tool_name = proposal.tool_name
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
                    and explicit_collection_query(request.utterance) is not None
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
                        _maybe_track_last_mentioned_item(
                            request.session_id, proposal, response_text, res
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
                            if order and not order.customer_name:
                                set_pending_action(
                                    request.session_id, "collect_customer_name"
                                )
                    elif proposal.tool_name == "confirm_order":
                        clear_pending_action(request.session_id)
                        confirmation_id = res["result"].get("confirmation_id", "")
                        response_text = (
                            "Your order is confirmed. "
                            f"Your confirmation ID is {confirmation_id}."
                        )
                    elif proposal.tool_name == "cancel_order":
                        clear_pending_action(request.session_id)
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
    append_turn_diagnostic(
        request.session_id,
        {
            "channel": request.channel.value,
            "twilio_call_sid": request.metadata.get("twilio_call_sid"),
            "raw_transcript": request.utterance,
            "normalized_transcript": normalized_utterance,
            "session_id": request.session_id,
            "deterministic_intent": deterministic_intent,
            "selected_tool_name": selected_tool_name
            or getattr(proposal, "tool_name", None),
            "routing_source": routing_source,
            "final_agent_text": response_text,
        },
    )

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
