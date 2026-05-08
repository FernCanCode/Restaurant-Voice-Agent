from pathlib import Path

import pytest
from starlette.requests import Request

import restaurant_agent.api as api_module
from restaurant_agent.api import (
    ingest_menu_file_endpoint,
    ingest_menu_text_endpoint,
    ingest_menu_url_endpoint,
    rebuild_index,
)


def _make_request(request_id: str = "req-menu") -> Request:
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/menu",
            "raw_path": b"/api/menu",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive=None,
    )
    request.state.request_id = request_id
    return request


@pytest.fixture(autouse=True)
def _menu_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MENU_DATA_PATH", str(tmp_path / "menu.json"))
    monkeypatch.setenv("MENU_INDEX_PATH", str(tmp_path / "index"))
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "super-secret-token")


def _fixture_html() -> str:
    return Path("data/raw/sample_restaurant_menu.html").read_text(encoding="utf-8")


class FakeUploadFile:
    def __init__(self, filename: str, content: str) -> None:
        self.filename = filename
        self._content = content.encode("utf-8")

    async def read(self) -> bytes:
        return self._content

    async def close(self) -> None:
        return None


def test_ingest_text_html_returns_item_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_module,
        "build_rag_index",
        lambda *args, **kwargs: {"degraded_mode": True},
    )

    response = ingest_menu_text_endpoint(
        _make_request("req-ingest-text"),
        {"text": _fixture_html(), "rebuild_index": True},
    )

    assert response["status"] == "success"
    assert response["item_count"] == 10
    assert response["index_rebuilt"] is True
    assert response["request_id"] == "req-ingest-text"
    assert Path(response["output_path"]).exists()
    assert "super-secret-token" not in str(response)


def test_ingest_url_can_be_monkeypatched_without_live_internet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(
        api_module.httpx,
        "get",
        lambda *args, **kwargs: FakeResponse(_fixture_html()),
    )

    response = ingest_menu_url_endpoint(
        _make_request("req-ingest-url"),
        {"url": "https://example.com/menu.html", "rebuild_index": False},
    )

    assert response["status"] == "success"
    assert response["item_count"] == 10
    assert response["index_rebuilt"] is False
    assert response["request_id"] == "req-ingest-url"


@pytest.mark.asyncio
async def test_ingest_file_accepts_html_upload() -> None:
    upload = FakeUploadFile(filename="menu.html", content=_fixture_html())

    response = await ingest_menu_file_endpoint(
        _make_request("req-ingest-file"),
        file=upload,
        rebuild_index=False,
    )

    assert response["status"] == "success"
    assert response["item_count"] == 10
    assert response["index_rebuilt"] is False
    assert response["request_id"] == "req-ingest-file"


def test_rebuild_index_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api_module,
        "build_rag_index",
        lambda *args, **kwargs: {"index_version": "1.0", "degraded_mode": True},
    )

    response = rebuild_index()

    assert response["status"] == "success"
    assert response["metadata"]["index_version"] == "1.0"
