"""Twilio-compatible helpers for the phone voice interface."""

from typing import Mapping
from xml.sax.saxutils import escape

from restaurant_agent.config import get_settings


def _twiml_document(body: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'


def build_gather_response(message: str, action_url: str = "/voice/turn") -> str:
    safe_message = escape(message)
    safe_action_url = escape(action_url, {'"': "&quot;"})
    # Twilio phone latency is influenced both by network/STT turnaround and by
    # how long Gather waits for speech or trailing silence. These settings keep
    # voice turns responsive without cutting callers off too aggressively.
    return _twiml_document(
        (
            f'<Gather input="speech" action="{safe_action_url}" method="POST" '
            'speechTimeout="auto" timeout="4">'
            f"<Say>{safe_message}</Say>"
            "</Gather>"
        )
    )


def build_say_response(message: str) -> str:
    return build_gather_response(message)


def build_goodbye_response(message: str) -> str:
    safe_message = escape(message)
    return _twiml_document(f"<Say>{safe_message}</Say><Hangup />")


def extract_twilio_call_sid(form_data: Mapping[str, object]) -> str | None:
    call_sid = form_data.get("CallSid")
    if call_sid is None:
        return None
    call_sid_str = str(call_sid).strip()
    return call_sid_str or None


def extract_speech_result(form_data: Mapping[str, object]) -> str:
    speech_result = form_data.get("SpeechResult")
    if speech_result is None:
        return ""
    return str(speech_result).strip()


def is_twilio_configured() -> bool:
    settings = get_settings()
    return bool(
        settings.enable_twilio
        and settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_phone_number
        and settings.twilio_webhook_base_url
    )
