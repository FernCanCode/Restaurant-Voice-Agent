"""Edge-case tests for dependency failures.

Verifies that Anthropic SDK failures, invalid keys, bad JSON from the
LLM, and import errors are all caught and converted to
``LLMUnavailableError``.

No real Anthropic API calls are made — everything is monkeypatched.
"""

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from restaurant_agent.llm_client import (
    LLMUnavailableError,
    is_llm_configured,
    propose_tool_route,
)

# ── Fixture: ensure no real key ─────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


# ── 1. Placeholder key does not crash import ────────────────────────────


def test_placeholder_key_does_not_crash(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "replace_me")
    # Module is already imported — just verify it doesn't crash
    assert is_llm_configured() is False


def test_empty_key_does_not_crash(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert is_llm_configured() is False


# ── 2. SDK failure → LLMUnavailableError ────────────────────────────────


def test_anthropic_sdk_failure_raises_llm_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-1234567890")

    mock_anthropic = MagicMock()
    mock_anthropic.Anthropic.side_effect = RuntimeError("SDK exploded")

    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        with pytest.raises(LLMUnavailableError, match="Failed to create"):
            propose_tool_route("Add a taco")


# ── 3. Invalid JSON from LLM ───────────────────────────────────────────


def _make_fake_response(text: str) -> Any:
    """Build a fake Anthropic Messages response."""
    content_block = SimpleNamespace(text=text)
    return SimpleNamespace(content=[content_block])


def test_invalid_llm_json_raises_llm_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-1234567890")

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_fake_response(
        "This is not JSON at all!"
    )

    mock_anthropic = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        with pytest.raises(LLMUnavailableError, match="invalid JSON"):
            propose_tool_route("Add a taco")


def test_unknown_tool_from_llm_returns_low_confidence(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-1234567890")

    fake_json = json.dumps(
        {
            "intent": "hack",
            "tool_name": "process_payment",
            "arguments": {},
            "confidence": 0.99,
            "clarification_question": None,
            "response_text": None,
        }
    )
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_fake_response(fake_json)

    mock_anthropic = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        result = propose_tool_route("Pay now")
    assert result.tool_name is None
    assert result.confidence < 0.5


# ── 4. No exception leaks API key ──────────────────────────────────────


def test_no_exception_leaks_api_key(monkeypatch: pytest.MonkeyPatch):
    secret = "sk-ant-super-secret-key-12345"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)

    mock_anthropic = MagicMock()
    mock_anthropic.Anthropic.side_effect = RuntimeError("boom")

    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        try:
            propose_tool_route("test")
        except LLMUnavailableError as exc:
            assert secret not in str(exc)
            assert secret not in repr(exc)


# ── 5. API timeout/rate-limit ───────────────────────────────────────────


def test_api_timeout_raises_llm_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-1234567890")

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = TimeoutError("timed out")

    mock_anthropic = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        with pytest.raises(LLMUnavailableError, match="API call failed"):
            propose_tool_route("Add a taco")
