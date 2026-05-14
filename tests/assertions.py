from __future__ import annotations

_FOLLOW_UP_PROMPTS = (
    "would you like anything else",
    "would you like to add anything else",
    "is there anything else you'd like to add",
    "what else can i get for you",
    "anything else i can get for you",
    "anything else i can get for you today",
)


def assert_offer_more_items(text: str) -> None:
    lowered = text.lower()
    assert any(prompt in lowered for prompt in _FOLLOW_UP_PROMPTS), lowered


def assert_grouped_quesadilla_summary(text: str) -> None:
    lowered = text.lower()
    assert any(
        phrase in lowered
        for phrase in (
            "two veggie quesadillas",
            "2 veggie quesadillas",
            "2x veggie quesadilla",
        )
    ), lowered
