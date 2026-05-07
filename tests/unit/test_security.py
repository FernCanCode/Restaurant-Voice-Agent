from restaurant_agent.security import redact_secrets


def test_redact_secrets():
    data = {
        "api_key": "123",
        "auth_token": "abc",
        "nested": {"password": "pwd", "public": "info"},
        "safe_list": [{"secret_card_cvv": "999"}, {"safe": "value"}],
    }

    redacted = redact_secrets(data)

    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["auth_token"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["public"] == "info"
    assert redacted["safe_list"][0]["secret_card_cvv"] == "[REDACTED]"
    assert redacted["safe_list"][1]["safe"] == "value"


def test_no_mutation():
    data = {"secret_key": "123"}
    redacted = redact_secrets(data)
    assert data["secret_key"] == "123"
    assert redacted["secret_key"] == "[REDACTED]"
