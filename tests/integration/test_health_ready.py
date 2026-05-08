from restaurant_agent.api import (
    get_browser_ui,
    health_check,
    readiness_check,
    status_check,
)


def test_health_check() -> None:
    data = health_check()
    assert data["status"] == "ok"
    assert data["service"] == "restaurant-voice-agent"
    assert "version" in data


def test_ready_check() -> None:
    data = readiness_check()
    assert "menu" in data
    assert "rag" in data


def test_ui_routes() -> None:
    res_root = get_browser_ui()
    assert res_root.status_code == 200
    assert "text/html" in res_root.headers.get("content-type", "")
    html = res_root.body.decode("utf-8")
    assert "Start Voice Order" in html
    assert "Speak" in html
    assert "Typed fallback" in html
    assert "Auto-listen after agent responses" in html
    assert "Chrome or Chromium" in html
    assert "Embedded previews may block microphone permissions" in html
    assert "Browser speech recognition does not expose a sensitivity control" in html
    assert "cleanTextForSpeech" in html


def test_status_check_redacts_secrets() -> None:
    data = status_check()
    assert isinstance(data, dict)
    if "anthropic_api_key" in data and data["anthropic_api_key"] is not None:
        assert data["anthropic_api_key"] == "[REDACTED]"
