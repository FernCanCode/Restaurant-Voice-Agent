"""Anthropic Claude wrapper with safe degradation.

This module wraps the Anthropic SDK to propose MCP tool routing and
generate natural-language response text. If the API key is missing,
a placeholder, or the API is unreachable, every public function raises
``LLMUnavailableError`` so that callers can fall back to the
deterministic ``fallback_parser`` module.

No Anthropic calls are made at import time.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from restaurant_agent.config import get_settings

logger = logging.getLogger(__name__)

_PLACEHOLDER_KEYS = {"", "replace_me", "your_key_here", "sk-placeholder", "CHANGE_ME"}


# ── Exceptions ──────────────────────────────────────────────────────────


class LLMUnavailableError(RuntimeError):
    """Raised when the Anthropic LLM cannot be reached or is misconfigured."""

    pass


# ── Response model ──────────────────────────────────────────────────────


class ToolRoutingProposal(BaseModel):
    intent: str
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = {}
    confidence: float = 0.0
    clarification_question: Optional[str] = None
    response_text: Optional[str] = None


# ── Public helpers ──────────────────────────────────────────────────────


def is_llm_configured() -> bool:
    """Return True only if a real Anthropic API key is present."""
    settings = get_settings()
    key = settings.anthropic_api_key
    if key is None:
        return False
    if key.strip() in _PLACEHOLDER_KEYS:
        return False
    return True


def _build_system_prompt(available_tools: List[Dict[str, Any]]) -> str:
    tool_names = [t["name"] for t in available_tools]
    return (
        "You are a restaurant ordering assistant for Cedar & Lime Taqueria.\n"
        "You help customers place food orders over voice or text.\n\n"
        "RULES — you MUST follow all of these:\n"
        "1. You may ONLY propose one of these tools: " + ", ".join(tool_names) + "\n"
        "2. Return a single JSON object with these exact keys:\n"
        "   intent, tool_name, arguments, confidence, clarification_question,"
        " response_text\n"
        "3. Do NOT compute totals — use the compute_total tool.\n"
        "4. Do NOT invent prices, allergens, or menu items.\n"
        "5. Do NOT process payment.\n"
        "6. If the user's intent is ambiguous, set confidence < 0.5 and "
        "provide a clarification_question.\n"
        "7. confidence must be a float between 0.0 and 1.0.\n"
        "8. Return ONLY the JSON object, no markdown fences, no extra text.\n"
    )


def _get_anthropic_client() -> Any:
    """Lazily create the Anthropic client. Raises LLMUnavailableError on failure."""
    if not is_llm_configured():
        raise LLMUnavailableError("Anthropic API key is not configured")

    try:
        import anthropic  # type: ignore[import-untyped]
    except ImportError as exc:
        raise LLMUnavailableError(f"Anthropic SDK not installed: {exc}") from exc

    settings = get_settings()
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return client
    except Exception as exc:
        # Never leak the key in the exception message
        raise LLMUnavailableError("Failed to create Anthropic client") from exc


# ── Public API ──────────────────────────────────────────────────────────


def propose_tool_route(
    utterance: str,
    session_context: Optional[Dict[str, Any]] = None,
    available_tools: Optional[List[Dict[str, Any]]] = None,
    request_id: Optional[str] = None,
) -> ToolRoutingProposal:
    """Ask the LLM which MCP tool to call for the given user utterance.

    Raises ``LLMUnavailableError`` if the LLM is unreachable so that the
    caller can fall back to ``fallback_parser.parse_fallback_intent``.
    """
    if available_tools is None:
        from restaurant_agent.mcp_server import list_tools

        available_tools = list_tools()

    client = _get_anthropic_client()  # raises LLMUnavailableError
    settings = get_settings()
    system_prompt = _build_system_prompt(available_tools)

    user_message = f"User utterance: {utterance}"
    if session_context:
        user_message += f"\n\nSession context: {json.dumps(session_context)}"

    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = response.content[0].text.strip()
    except Exception as exc:
        # Catch timeout, rate-limit, network, etc.
        raise LLMUnavailableError(f"Anthropic API call failed: {exc}") from exc

    # Parse the LLM's JSON response
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON: %s", raw_text[:200])
        raise LLMUnavailableError("LLM returned invalid JSON")

    # Validate tool_name against registry
    valid_tool_names = {t["name"] for t in available_tools}
    proposed_tool = data.get("tool_name")
    if proposed_tool and proposed_tool not in valid_tool_names:
        logger.warning("LLM proposed unknown tool: %s", proposed_tool)
        return ToolRoutingProposal(
            intent=data.get("intent", "unknown"),
            tool_name=None,
            arguments={},
            confidence=0.1,
            clarification_question=(
                "I'm not sure what you'd like to do. Could you rephrase?"
            ),
            response_text=None,
        )

    return ToolRoutingProposal(
        intent=data.get("intent", "unknown"),
        tool_name=data.get("tool_name"),
        arguments=data.get("arguments", {}),
        confidence=float(data.get("confidence", 0.5)),
        clarification_question=data.get("clarification_question"),
        response_text=data.get("response_text"),
    )


def generate_response_text(
    utterance: str,
    tool_result: Optional[Dict[str, Any]] = None,
    session_context: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> str:
    """Generate a natural-language response to speak or display to the user.

    Raises ``LLMUnavailableError`` if the LLM is unreachable.
    """
    client = _get_anthropic_client()
    settings = get_settings()

    system = (
        "You are a friendly restaurant ordering assistant for Cedar & Lime Taqueria. "
        "Summarise the tool result for the customer in a natural, conversational way. "
        "Do NOT invent prices, allergens, or menu items. "
        "Do NOT process payment. Keep it concise."
    )

    user_msg = f"Customer said: {utterance}"
    if tool_result:
        user_msg += f"\n\nTool result: {json.dumps(tool_result)}"
    if session_context:
        user_msg += f"\n\nSession context: {json.dumps(session_context)}"

    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        return str(response.content[0].text.strip())
    except Exception as exc:
        raise LLMUnavailableError(f"Anthropic API call failed: {exc}") from exc
