from typing import Any, Dict

SENSITIVE_KEYS = {"key", "token", "secret", "password", "auth", "card", "cvv"}


def _is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    return any(sensitive in key_lower for sensitive in SENSITIVE_KEYS)


def redact_secrets(data: Any) -> Any:
    """
    Recursively iterate over a dictionary or list and redact values for sensitive keys.
    Returns a safe copy, does not mutate input.
    """
    if isinstance(data, dict):
        redacted_dict: Dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(k, str) and _is_sensitive_key(k):
                redacted_dict[k] = "[REDACTED]"
            else:
                redacted_dict[k] = redact_secrets(v)
        return redacted_dict
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    else:
        return data
