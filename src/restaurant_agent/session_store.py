import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from restaurant_agent.schemas import Channel, DialogueMode, DialogueState, DialogueTurn

# In-memory storage
_SESSIONS: Dict[str, DialogueState] = {}


def _generate_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:8]}"


def create_session(
    channel: Channel = Channel.browser,
    caller_id: Optional[str] = None,
    twilio_call_sid: Optional[str] = None,
) -> DialogueState:
    session_id = _generate_session_id()
    state = DialogueState(
        session_id=session_id,
        channel=channel,
        twilio_call_sid=twilio_call_sid,
        dialogue_mode=DialogueMode.GREETING,
        awaiting_final_confirmation=False,
        order_readback_required=False,
        degraded_llm=False,
        degraded_retrieval=False,
    )
    _SESSIONS[session_id] = state
    return state


def get_session(session_id: str) -> Optional[DialogueState]:
    return _SESSIONS.get(session_id)


def update_session(state: DialogueState) -> DialogueState:
    _SESSIONS[state.session_id] = state
    return state


def append_turn(
    session_id: str, role: str, content: str, request_id: Optional[str] = None
) -> DialogueState:
    state = get_session(session_id)
    if not state:
        raise ValueError(f"Session not found: {session_id}")

    turn = DialogueTurn(
        role=role,
        content=content,
        timestamp=datetime.now(timezone.utc).isoformat(),
        request_id=request_id,
    )
    state.turns.append(turn)

    if request_id and request_id not in state.request_ids:
        state.request_ids.append(request_id)

    return update_session(state)


def set_dialogue_mode(session_id: str, mode: DialogueMode) -> DialogueState:
    state = get_session(session_id)
    if not state:
        raise ValueError(f"Session not found: {session_id}")
    state.dialogue_mode = mode
    return update_session(state)


def find_session_by_twilio_call_sid(twilio_call_sid: str) -> Optional[DialogueState]:
    for state in _SESSIONS.values():
        if state.twilio_call_sid == twilio_call_sid:
            return state
    return None


def list_recent_sessions(limit: int = 20) -> List[DialogueState]:
    return list(_SESSIONS.values())[-limit:]


def clear_sessions() -> None:
    _SESSIONS.clear()
