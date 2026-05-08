"""Integration tests for degraded mode.

Verifies that when no Anthropic key is configured, the system degrades
gracefully: ``is_llm_configured()`` returns False, ``propose_tool_route``
raises ``LLMUnavailableError``, and the fallback parser can handle the
request instead.

No real Anthropic API calls are made.
"""

import pytest

from restaurant_agent.fallback_parser import parse_fallback_intent
from restaurant_agent.llm_client import (
    LLMUnavailableError,
    is_llm_configured,
    propose_tool_route,
)


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no real key is present during these tests."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")


def test_is_llm_configured_false_when_no_key():
    assert is_llm_configured() is False


def test_is_llm_configured_false_for_placeholder(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "replace_me")
    assert is_llm_configured() is False


def test_propose_tool_route_raises_when_key_missing():
    with pytest.raises(LLMUnavailableError, match="not configured"):
        propose_tool_route("Add two chicken tacos")


def test_fallback_produces_safe_add_proposal():
    """The fallback parser can handle a simple add-item utterance."""
    result = parse_fallback_intent(
        "Add two chicken tacos",
        session_context={"session_id": "sess_test"},
    )
    assert result.tool_name == "add_order_item"
    assert result.arguments["item_id"] == "chicken_tacos"
    assert result.arguments["quantity"] == 2
    assert result.safe_to_execute is True


def test_fallback_refuses_ambiguous_mutation():
    """The fallback parser rejects an ambiguous remove request."""
    result = parse_fallback_intent(
        "Remove that thing I said earlier",
        session_context={"session_id": "sess_test"},
    )
    assert result.safe_to_execute is False
    assert result.clarification_question is not None


def test_degraded_flow_pattern():
    """Demonstrates the intended try/except degraded flow."""
    utterance = "I'd like a carnitas burrito"
    try:
        propose_tool_route(utterance)
        pytest.fail("Should have raised LLMUnavailableError")
    except LLMUnavailableError:
        result = parse_fallback_intent(
            utterance, session_context={"session_id": "sess_demo"}
        )
    assert result.tool_name == "add_order_item"
    assert result.arguments["item_id"] == "carnitas_burrito"
    assert result.safe_to_execute is True
