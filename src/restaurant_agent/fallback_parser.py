"""Deterministic fallback parser for degraded mode.

When the Anthropic LLM is unavailable, this module uses simple keyword
matching and regex to propose MCP tool routing for high-confidence
requests.  It never mutates order state — it only returns a proposal
that the caller can forward to ``mcp_server.call_tool()``.

Low-confidence or ambiguous utterances are flagged with
``safe_to_execute=False`` and a clarification question.
"""

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from restaurant_agent.menu_retriever import (
    explicit_dietary_tag_query,
    is_explicit_taco_category_query,
)

# ── Response model ──────────────────────────────────────────────────────


class ParsedFallbackIntent(BaseModel):
    intent: str
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = {}
    confidence: float = 0.0
    clarification_question: Optional[str] = None
    response_text: Optional[str] = None
    safe_to_execute: bool = False


# ── Item name → id mapping for the known menu fixture ───────────────────

_ITEM_MAP: Dict[str, str] = {
    "chicken tacos": "chicken_tacos",
    "chicken taco": "chicken_tacos",
    "crispy fish tacos": "crispy_fish_tacos",
    "crispy fish taco": "crispy_fish_tacos",
    "fish tacos": "crispy_fish_tacos",
    "fish taco": "crispy_fish_tacos",
    "black bean bowl": "black_bean_bowl",
    "carnitas burrito": "carnitas_burrito",
    "carnitas burritos": "carnitas_burrito",
    "burrito": "carnitas_burrito",
    "burritos": "carnitas_burrito",
    "veggie quesadilla": "veggie_quesadilla",
    "quesadilla": "veggie_quesadilla",
    "quesadillas": "veggie_quesadilla",
    "classic burger": "classic_burger",
    "burger": "classic_burger",
    "burgers": "classic_burger",
    "street corn": "street_corn",
    "chips and salsa": "chips_and_salsa",
    "chips & salsa": "chips_and_salsa",
    "lemonade": "lemonade",
    "lemonades": "lemonade",
    "horchata": "horchata",
    "horchatas": "horchata",
}

_WORD_TO_NUM: Dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "a": 1,
    "an": 1,
}

# Known special-instruction modifiers that are always safe
_KNOWN_SPECIAL_INSTRUCTIONS = {
    "no onions",
    "no cilantro",
    "no cheese",
    "no sour cream",
    "extra salsa",
    "extra rice",
    "extra beans",
    "mild salsa",
    "spicy",
    "extra spicy",
}

# Modifications that need confirmation because they aren't guaranteed priced
_NEEDS_CONFIRMATION_MODS = {
    "extra queso",
    "extra guac",
    "extra avocado",
}

_ADD_REQUEST_PREFIXES = [
    r"add",
    r"order",
    r"could i get",
    r"can i get",
    r"can i have",
    r"i would like",
    r"i'd like",
    r"ill take",
    r"i'll take",
    r"let me get",
    r"give me",
    r"i'll have",
    r"ill have",
    r"we'll have",
    r"i want",
]

_NAME_FILLER_WORDS = {
    "the",
    "name",
    "under",
    "it",
    "order",
    "put",
    "my",
    "is",
    "its",
    "it's",
}

_PRONOUN_FOLLOWUP_PATTERNS = [
    r"i'll take one of those",
    r"i'll take \d+ of those",
    r"ill take one of those",
    r"ill take \d+ of those",
    r"i will take one of those",
    r"i will take \d+ of those",
    r"i'll take one of those please",
    r"i'll take \d+ of those please",
    r"ill take one of those please",
    r"ill take \d+ of those please",
    r"i'll take that",
    r"ill take that",
    r"i'll take one",
    r"ill take one",
    r"i'll have that",
    r"ill have that",
    r"i'll have one of those",
    r"i'll have \d+ of those",
    r"ill have one of those",
    r"ill have \d+ of those",
    r"i'll have one of them",
    r"ill have one of them",
    r"i'll get one of those",
    r"i'll get \d+ of those",
    r"ill get one of those",
    r"ill get \d+ of those",
    r"can i get one of those",
    r"can i get \d+ of those",
    r"give me one of those",
    r"give me \d+ of those",
    r"i'll take one of them",
    r"ill take one of them",
    r"i will take one of them",
    r"one of those",
    r"\d+ of those",
    r"that one",
    r"i'll take that one",
    r"ill take that one",
    r"i'll take it",
    r"ill take it",
    r"give me that",
    r"add one of those",
    r"add that",
    r"i want that",
    r"i want one of those",
]


# ── Helpers ─────────────────────────────────────────────────────────────


def _extract_quantity(text: str) -> int:
    """Try to pull a quantity from the beginning portion of an add request."""
    for word, num in _WORD_TO_NUM.items():
        pattern = rf"\b{word}\b"
        if re.search(pattern, text, re.IGNORECASE):
            return num
    m = re.search(r"\b(\d+)\b", text)
    if m:
        return int(m.group(1))
    return 1


def _match_item(text: str) -> Optional[str]:
    """Find the best-matching menu item id in *text*, longest match first."""
    lower = text.lower()
    for name in sorted(_ITEM_MAP.keys(), key=len, reverse=True):
        if name in lower:
            return _ITEM_MAP[name]
    return None


def match_menu_item_id(text: str) -> Optional[str]:
    """Public wrapper for deterministic menu-item matching."""
    return _match_item(_normalize_text(text))


def _extract_special_instructions(text: str) -> List[str]:
    """Pull known modification phrases from the utterance."""
    lower = text.lower()
    found: List[str] = []
    for mod in sorted(_KNOWN_SPECIAL_INSTRUCTIONS, key=len, reverse=True):
        if mod in lower:
            found.append(mod)
    return found


def _extract_needs_confirmation_mods(text: str) -> List[str]:
    """Pull modifications that need explicit user confirmation."""
    lower = text.lower()
    found: List[str] = []
    for mod in sorted(_NEEDS_CONFIRMATION_MODS, key=len, reverse=True):
        if mod in lower:
            found.append(mod)
    return found


def _extract_customer_name(text: str) -> Optional[str]:
    """Try to extract a customer name from phrases like 'under Fernando'."""
    patterns = [
        r"(?:put(?: it)? under(?: the name)?|under(?: the name)?|the name is|name is|name's|my name is|it's|it is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\s*$",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = " ".join(word.capitalize() for word in m.group(1).split())
            if candidate and candidate.lower() not in _NAME_FILLER_WORDS:
                return candidate
    return None


def _extract_bare_name(text: str) -> Optional[str]:
    candidate = text.strip().replace("’", "'")
    candidate = re.sub(r"^[\"'“”‘’\s]+|[\"'“”‘’.,!?;:\s]+$", "", candidate)
    if not candidate or len(candidate) > 40:
        return None

    if not re.fullmatch(r"[A-Za-z]+(?:\s+[A-Za-z]+){0,2}", candidate):
        return None

    lowered_words = {word.lower() for word in candidate.split()}
    if lowered_words & _NAME_FILLER_WORDS:
        return None

    return " ".join(word.capitalize() for word in candidate.split())


def _normalize_text(text: str) -> str:
    """Lowercase and collapse punctuation/whitespace for intent matching."""
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    normalized = re.sub(r"[^\w\s']", " ", text.lower())
    normalized = " ".join(normalized.split())
    normalized = re.sub(r"\bill(?=\s+(?:take|have|get|want)\b)", "i'll", normalized)
    normalized = re.sub(r"\bi\s+will(?=\s+take\b)", "i will", normalized)
    normalized = re.sub(r"\bwell(?=\s+have\b)", "we'll", normalized)
    normalized = re.sub(r"\s+please$", "", normalized)
    return normalized


def _extract_unknown_add_target(normalized: str) -> Optional[str]:
    stripped = _strip_add_prefix(normalized)
    stripped = re.sub(r"^(?:\d+|one|two|three|four|five|a|an)\b", "", stripped).strip()
    stripped = re.sub(r"^(?:the|a|an|my)\b", "", stripped).strip()
    stripped = re.split(r"\bwith\b|\bwithout\b|\bno\b", stripped, maxsplit=1)[0].strip()
    stripped = stripped.strip(" .'\"")
    if not stripped:
        return None
    if len(stripped.split()) > 5:
        return None
    return stripped


def _matches_any_pattern(text: str, patterns: List[str]) -> bool:
    return any(re.fullmatch(pattern, text) for pattern in patterns)


def _is_conversation_done(normalized: str) -> bool:
    done_patterns = [
        r"no",
        r"no thanks",
        r"that's all",
        r"okay that's all",
        r"ok that's all",
        r"that is all",
        r"okay that is all",
        r"ok that is all",
        r"that's it",
        r"okay that's it",
        r"ok that's it",
        r"that is it",
        r"okay that is it",
        r"ok that is it",
        r"no that's all",
        r"no that is all",
        r"no that's it",
        r"no that is it",
        r"no thanks that's all",
        r"no thanks that's it",
        r"that's everything",
        r"that is everything",
        r"i'm done",
        r"okay i'm done",
        r"ok i'm done",
        r"okay im done",
        r"ok im done",
        r"im done",
        r"no i'm done",
        r"no im done",
        r"i am done",
        r"i'm done ordering",
        r"im done ordering",
        r"i am done ordering",
        r"done ordering",
        r"i'm finished",
        r"im finished",
        r"i am finished",
        r"finished",
        r"finished ordering",
        r"i'm finished ordering",
        r"im finished ordering",
        r"done",
        r"all done",
        r"that'll be all",
        r"that will be all",
        r"nothing else",
        r"no nothing else",
        r"i'm ready",
        r"im ready",
        r"i am ready",
        r"i'm ready to proceed",
        r"im ready to proceed",
        r"i am ready to proceed",
        r"ready to proceed",
        r"complete order",
        r"complete my order",
        r"finish order",
        r"finish my order",
        r"checkout",
        r"check out",
        r"i'm ready to checkout",
        r"im ready to checkout",
        r"ready to checkout",
        r"ready to finish",
        r"ready to complete",
    ]
    return _matches_any_pattern(normalized, done_patterns)


def _is_confirm_request(normalized: str) -> bool:
    confirm_patterns = [
        r"yes",
        r"yes confirm",
        r"yes confirm the order",
        r"confirm",
        r"confirm order",
        r"confirm my order",
        r"confirm the order",
        r"yes confirm order",
        r"yes confirm my order",
        r"yes, confirm",
        r"yes that's correct",
        r"yes thats correct",
        r"yes that's right",
        r"yes thats right",
        r"yes place the order",
        r"yes place it",
        r"place the order",
        r"go ahead and confirm",
    ]
    return _matches_any_pattern(normalized, confirm_patterns)


def _has_add_request_prefix(normalized: str) -> bool:
    return any(
        re.search(rf"\b{prefix}\b", normalized) for prefix in _ADD_REQUEST_PREFIXES
    )


def _looks_like_add_request(normalized: str, item_id: Optional[str]) -> bool:
    if _has_add_request_prefix(normalized):
        return True

    return bool(
        item_id and re.match(r"^(?:\d+|one|two|three|four|five|a|an)\b", normalized)
    )


def _is_broad_add_request(normalized: str) -> bool:
    broad_add_patterns = [
        r"give me one of each of those",
        r"give me one of each",
        r"one of each of those",
        r"one of each of them",
        r"all of them",
        r"all of those",
        r"all of that",
        r"give me all of it",
        r"give me all of that",
        r"give me all of those",
        r"give me all of them",
        r"i want all of it",
        r"i want all of that",
        r"i want all of those",
        r"i want all of them",
        r"i want every single item",
        r"i'll take all of them",
        r"i'll take all of that",
        r"add all of them",
        r"add all of it",
        r"add all of that",
        r"one of each",
    ]
    return _matches_any_pattern(normalized, broad_add_patterns)


def _is_price_lookup_request(normalized: str, item_id: Optional[str]) -> bool:
    if not item_id:
        return False

    if "my total" in normalized or "order total" in normalized:
        return False

    price_patterns = [
        r"how much is .+",
        r"how much are .+",
        r"what does .+ cost",
        r"what is the price of .+",
    ]
    return any(re.fullmatch(pattern, normalized) for pattern in price_patterns)


def _is_contextual_item_followup(normalized: str) -> bool:
    return _matches_any_pattern(normalized, _PRONOUN_FOLLOWUP_PATTERNS)


def _strip_add_prefix(text: str) -> str:
    stripped = text.strip()
    for prefix in _ADD_REQUEST_PREFIXES:
        stripped = re.sub(rf"^{prefix}\b", "", stripped, flags=re.IGNORECASE).strip()
    return stripped


def _parse_multi_item_add_request(
    text: str, ctx: Dict[str, Any]
) -> Optional[ParsedFallbackIntent]:
    base = _strip_add_prefix(_normalize_text(text))
    segments = [
        segment.strip(" ,.")
        for segment in re.split(r"\band\b", base)
        if segment.strip(" ,.")
    ]
    if len(segments) < 2:
        return None

    items: List[Dict[str, Any]] = []
    unresolved: List[str] = []
    for segment in segments:
        item_id = _match_item(segment)
        if not item_id:
            unresolved.append(segment)
            continue

        needs_confirm = _extract_needs_confirmation_mods(segment)
        if needs_confirm:
            return ParsedFallbackIntent(
                intent="add_multiple_items",
                tool_name=None,
                arguments={},
                confidence=0.4,
                clarification_question=(
                    f"I do not see {needs_confirm[0]} as a listed priced option. "
                    "Should I add it as a special instruction?"
                ),
                safe_to_execute=False,
            )

        items.append(
            {
                "session_id": ctx.get("session_id", ""),
                "item_id": item_id,
                "quantity": _extract_quantity(segment),
                "special_instructions": _extract_special_instructions(segment),
            }
        )

    if unresolved:
        return ParsedFallbackIntent(
            intent="add_multiple_items",
            tool_name=None,
            arguments={},
            confidence=0.3,
            clarification_question=(
                "I could not tell which menu items you meant for "
                + ", ".join(unresolved)
                + ". Which items would you like to add?"
            ),
            safe_to_execute=False,
        )

    if len(items) >= 2:
        return ParsedFallbackIntent(
            intent="add_multiple_items",
            tool_name=None,
            arguments={"items": items},
            confidence=0.9,
            safe_to_execute=True,
        )

    return None


def _should_treat_as_item_followup(ctx: Dict[str, Any]) -> bool:
    pending_action = str(ctx.get("pending_action") or "")
    if pending_action in {
        "collect_customer_name",
        "confirm_add_all",
        "confirm_add_special_instruction",
        "clarify_remove_item",
    }:
        return False

    last_intent = str(ctx.get("last_intent") or "")
    last_agent_response = str(ctx.get("last_agent_response") or "").lower()
    if "remove" in last_agent_response:
        return False
    if last_intent == "search_menu":
        return True

    followup_markers = [
        "which item",
        "what item",
        "options are",
        "we have",
        "what would you like to add",
    ]
    return any(marker in last_agent_response for marker in followup_markers)


# ── Main entry point ────────────────────────────────────────────────────


def parse_fallback_intent(
    utterance: str,
    session_context: Optional[Dict[str, Any]] = None,
) -> ParsedFallbackIntent:
    """Parse *utterance* into a proposed MCP tool call without an LLM.

    Returns ``safe_to_execute=True`` only for high-confidence,
    unambiguous intents.  The caller should route the proposal through
    ``mcp_server.call_tool()`` when safe, or surface the clarification
    question otherwise.
    """
    text = utterance.strip()
    lower = text.lower()
    normalized = _normalize_text(text)
    ctx = session_context or {}
    item_id = _match_item(normalized)
    pending_action = str(ctx.get("pending_action") or "")

    # ── Payment refusal ─────────────────────────────────────────────
    if any(
        kw in lower
        for kw in ["pay", "payment", "charge", "credit card", "debit", "venmo"]
    ):
        return ParsedFallbackIntent(
            intent="payment_request",
            tool_name=None,
            arguments={},
            confidence=0.9,
            response_text=(
                "I'm sorry, I can't process payments. "
                "Please pay at the counter when you pick up your order."
            ),
            safe_to_execute=False,
        )

    # ── Allergy guarantee refusal ───────────────────────────────────
    allergy_kws = ["allergy", "allergic", "allergen", "safe for"]
    guarantee_kws = ["guarantee", "promise", "100%", "absolutely"]
    if any(kw in lower for kw in allergy_kws):
        if any(kw in lower for kw in guarantee_kws):
            return ParsedFallbackIntent(
                intent="allergy_guarantee_request",
                tool_name=None,
                arguments={},
                confidence=0.8,
                response_text=(
                    "I cannot guarantee that any item is free of allergens. "
                    "Please check with the kitchen staff for allergy safety."
                ),
                safe_to_execute=False,
            )
        # Route to check_dietary_info if item + allergen are identifiable
        if item_id:
            return ParsedFallbackIntent(
                intent="check_dietary",
                tool_name="check_dietary_info",
                arguments={
                    "item_id": item_id,
                    "question": text,
                    "allergen": text,
                },
                confidence=0.6,
                safe_to_execute=True,
            )

    # ── Cancel order ────────────────────────────────────────────────
    if re.search(r"\bcancel\b", lower) and item_id is None:
        session_id = ctx.get("session_id")
        if session_id:
            return ParsedFallbackIntent(
                intent="cancel_order",
                tool_name="cancel_order",
                arguments={"session_id": session_id},
                confidence=0.9,
                safe_to_execute=True,
            )
        return ParsedFallbackIntent(
            intent="cancel_order",
            tool_name="cancel_order",
            arguments={},
            confidence=0.7,
            clarification_question="Which order would you like to cancel?",
            safe_to_execute=False,
        )

    # ── Confirm order ───────────────────────────────────────────────
    if _is_confirm_request(normalized) and pending_action not in {
        "confirm_add_special_instruction",
        "clarify_remove_item",
    }:
        session_id = ctx.get("session_id")
        if session_id:
            return ParsedFallbackIntent(
                intent="confirm_order",
                tool_name="confirm_order",
                arguments={"session_id": session_id},
                confidence=0.8,
                safe_to_execute=True,
            )

    # ── Conversational wrap-up / done ───────────────────────────────
    if _is_conversation_done(normalized):
        return ParsedFallbackIntent(
            intent="conversation_done",
            tool_name=None,
            arguments={},
            confidence=0.8,
            safe_to_execute=True,
        )

    # ── Customer name capture ───────────────────────────────────────
    name = _extract_customer_name(text)
    if name:
        return ParsedFallbackIntent(
            intent="set_customer_name",
            tool_name=None,
            arguments={"customer_name": name},
            confidence=0.85,
            response_text=f"Got it, the order is under {name}.",
            safe_to_execute=True,
        )

    if str(ctx.get("pending_action") or "") == "collect_customer_name":
        bare_name = _extract_bare_name(text)
        if bare_name:
            return ParsedFallbackIntent(
                intent="set_customer_name",
                tool_name=None,
                arguments={"customer_name": bare_name},
                confidence=0.9,
                response_text=f"Got it, the order is under {bare_name}.",
                safe_to_execute=True,
            )

    if (
        _is_contextual_item_followup(normalized)
        and ctx.get("last_mentioned_item_id")
        and str(ctx.get("pending_action") or "") not in {"collect_customer_name"}
    ):
        return ParsedFallbackIntent(
            intent="add_order_item",
            tool_name="add_order_item",
            arguments={
                "session_id": ctx.get("session_id", ""),
                "item_id": ctx.get("last_mentioned_item_id"),
                "quantity": _extract_quantity(normalized),
                "special_instructions": [],
            },
            confidence=0.85,
            safe_to_execute=True,
        )

    # ── Order summary / readback ────────────────────────────────────
    if any(
        kw in lower
        for kw in [
            "read back",
            "readback",
            "what do i have",
            "what's in my order",
            "my order",
            "order summary",
            "what did i order",
            "show order",
            "review order",
        ]
    ):
        session_id = ctx.get("session_id")
        return ParsedFallbackIntent(
            intent="get_order_summary",
            tool_name="get_order_summary",
            arguments={"session_id": session_id} if session_id else {},
            confidence=0.85,
            safe_to_execute=bool(session_id),
            clarification_question=(
                None if session_id else "I need your session to look up the order."
            ),
        )

    # ── Item price lookup ───────────────────────────────────────────
    if _is_price_lookup_request(normalized, item_id):
        return ParsedFallbackIntent(
            intent="price_lookup",
            tool_name=None,
            arguments={"item_id": item_id},
            confidence=0.9,
            safe_to_execute=True,
        )

    # ── Compute total ───────────────────────────────────────────────
    if any(
        kw in lower for kw in ["total", "how much", "what do i owe", "price", "cost"]
    ):
        session_id = ctx.get("session_id")
        return ParsedFallbackIntent(
            intent="compute_total",
            tool_name="compute_total",
            arguments={"session_id": session_id} if session_id else {},
            confidence=0.85,
            safe_to_execute=bool(session_id),
            clarification_question=(
                None if session_id else "I need your session to compute the total."
            ),
        )

    # ── Remove item ─────────────────────────────────────────────────
    if re.search(r"\b(remove|delete|drop)\b", normalized) or (
        item_id
        and (
            "take off" in normalized
            or normalized.endswith(" off")
            or normalized.startswith("cancel ")
        )
    ):
        line_item_id = ctx.get("line_item_id")
        session_id = ctx.get("session_id")
        if line_item_id and session_id:
            return ParsedFallbackIntent(
                intent="remove_order_item",
                tool_name="remove_order_item",
                arguments={
                    "session_id": session_id,
                    "line_item_id": line_item_id,
                },
                confidence=0.8,
                safe_to_execute=True,
            )
        if item_id and session_id:
            return ParsedFallbackIntent(
                intent="remove_order_item_by_name",
                tool_name=None,
                arguments={"session_id": session_id, "item_id": item_id},
                confidence=0.8,
                safe_to_execute=True,
            )
        return ParsedFallbackIntent(
            intent="remove_order_item",
            tool_name=None,
            arguments={},
            confidence=0.3,
            clarification_question=(
                "Which item would you like to remove? "
                "I need the specific line item to remove it."
            ),
            safe_to_execute=False,
        )

    # ── Broad add request ───────────────────────────────────────────
    if _is_broad_add_request(normalized):
        return ParsedFallbackIntent(
            intent="broad_add_request",
            tool_name=None,
            arguments={},
            confidence=0.6,
            clarification_question="Do you mean one of each item I just listed?",
            safe_to_execute=False,
        )

    multi_item_intent = _parse_multi_item_add_request(text, ctx)
    if multi_item_intent is not None:
        return multi_item_intent

    # ── Add item ────────────────────────────────────────────────────
    if _looks_like_add_request(normalized, item_id):
        if item_id:
            quantity = _extract_quantity(lower)
            special_instructions = _extract_special_instructions(lower)
            needs_confirm = _extract_needs_confirmation_mods(lower)

            if needs_confirm:
                pending_special_instructions = list(
                    dict.fromkeys(special_instructions + needs_confirm)
                )
                return ParsedFallbackIntent(
                    intent="add_order_item",
                    tool_name="add_order_item",
                    arguments={
                        "session_id": ctx.get("session_id", ""),
                        "item_id": item_id,
                        "quantity": quantity,
                        "known_modification_names": [],
                        "special_instructions": pending_special_instructions,
                    },
                    confidence=0.5,
                    clarification_question=(
                        f"I do not see {needs_confirm[0]} as a listed priced"
                        " option. Should I add it as a special instruction?"
                    ),
                    safe_to_execute=False,
                )

            session_id = ctx.get("session_id", "")
            return ParsedFallbackIntent(
                intent="add_order_item",
                tool_name="add_order_item",
                arguments={
                    "session_id": session_id,
                    "item_id": item_id,
                    "quantity": quantity,
                    "known_modification_names": [],
                    "special_instructions": special_instructions,
                },
                confidence=0.85,
                safe_to_execute=True,
            )
        else:
            unknown_target = _extract_unknown_add_target(normalized)
            return ParsedFallbackIntent(
                intent="add_order_item",
                tool_name=None,
                arguments={},
                confidence=0.3,
                clarification_question=(
                    f"I don't see {unknown_target} on the menu. "
                    "You can ask what menu items we have or choose another item."
                    if unknown_target
                    else "I'm not sure which item you'd like to add. "
                    "Could you tell me the item name from the menu?"
                ),
                safe_to_execute=False,
            )

    if item_id and _should_treat_as_item_followup(ctx):
        session_id = ctx.get("session_id", "")
        return ParsedFallbackIntent(
            intent="add_order_item",
            tool_name="add_order_item",
            arguments={
                "session_id": session_id,
                "item_id": item_id,
                "quantity": 1,
                "known_modification_names": [],
                "special_instructions": _extract_special_instructions(lower),
            },
            confidence=0.8,
            safe_to_execute=True,
        )

    # ── Menu search ─────────────────────────────────────────────────
    if is_explicit_taco_category_query(text):
        return ParsedFallbackIntent(
            intent="search_menu",
            tool_name="search_menu",
            arguments={"query": text, "top_k": 5},
            confidence=0.8,
            safe_to_execute=True,
        )

    dietary_tag = explicit_dietary_tag_query(text)
    if dietary_tag and any(
        keyword in normalized
        for keyword in ["what", "kind", "items", "options", "have", "show", "menu"]
    ):
        return ParsedFallbackIntent(
            intent="search_menu",
            tool_name="search_menu",
            arguments={"query": text, "top_k": 8},
            confidence=0.8,
            safe_to_execute=True,
        )

    if any(
        keyword in normalized
        for keyword in ["drink", "drinks", "meat", "protein", "proteins"]
    ) and any(
        keyword in normalized
        for keyword in ["what", "which", "options", "have", "show", "menu"]
    ):
        return ParsedFallbackIntent(
            intent="search_menu",
            tool_name="search_menu",
            arguments={"query": text, "top_k": 8},
            confidence=0.8,
            safe_to_execute=True,
        )

    search_triggers = [
        r"\b(what|which|do you have|show me|menu|options|available|recommend)\b"
    ]
    if any(re.search(p, lower) for p in search_triggers):
        return ParsedFallbackIntent(
            intent="search_menu",
            tool_name="search_menu",
            arguments={"query": text, "top_k": 5},
            confidence=0.7,
            safe_to_execute=True,
        )

    # ── Update quantity ─────────────────────────────────────────────
    if re.search(r"\b(change|update|make it|switch to)\b.+\b\d+\b", lower):
        line_item_id = ctx.get("line_item_id")
        session_id = ctx.get("session_id")
        quantity = _extract_quantity(lower)
        if line_item_id and session_id:
            return ParsedFallbackIntent(
                intent="update_order_item",
                tool_name="update_order_item",
                arguments={
                    "session_id": session_id,
                    "line_item_id": line_item_id,
                    "quantity": quantity,
                },
                confidence=0.75,
                safe_to_execute=True,
            )
        return ParsedFallbackIntent(
            intent="update_order_item",
            tool_name=None,
            arguments={},
            confidence=0.3,
            clarification_question="Which item would you like to update?",
            safe_to_execute=False,
        )

    # ── Fallback: ambiguous ─────────────────────────────────────────
    return ParsedFallbackIntent(
        intent="unknown",
        tool_name=None,
        arguments={},
        confidence=0.1,
        clarification_question=(
            "I'm not sure what you'd like to do. "
            "You can ask to see the menu, add items, or check your order."
        ),
        safe_to_execute=False,
    )
