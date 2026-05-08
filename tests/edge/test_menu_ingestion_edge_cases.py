from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from restaurant_agent.api import (
    ingest_menu_file_endpoint,
    ingest_menu_text_endpoint,
    ingest_menu_url_endpoint,
)


def _make_request(request_id: str = "req-menu-edge") -> Request:
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


class FakeUploadFile:
    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content

    async def close(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _menu_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MENU_DATA_PATH", str(tmp_path / "menu.json"))
    monkeypatch.setenv("MENU_INDEX_PATH", str(tmp_path / "index"))
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "super-secret-token")


def test_ingest_text_rejects_empty_text() -> None:
    with pytest.raises(HTTPException, match="Text content is required"):
        ingest_menu_text_endpoint(
            _make_request(),
            {"text": "   ", "rebuild_index": False},
        )


def test_ingest_url_rejects_invalid_scheme() -> None:
    with pytest.raises(
        HTTPException,
        match="Only http and https URLs are supported for menu ingestion",
    ):
        ingest_menu_url_endpoint(
            _make_request(),
            {"url": "file:///tmp/menu.html", "rebuild_index": False},
        )


@pytest.mark.asyncio
async def test_ingest_file_rejects_unsupported_extension() -> None:
    upload = FakeUploadFile(filename="menu.pdf", content=b"fake pdf")

    with pytest.raises(HTTPException, match="Unsupported file extension"):
        await ingest_menu_file_endpoint(
            _make_request(),
            file=upload,
            rebuild_index=False,
        )


def test_ingestion_errors_do_not_expose_secrets() -> None:
    with pytest.raises(HTTPException) as exc_info:
        ingest_menu_url_endpoint(
            _make_request(),
            {"url": "file:///tmp/menu.html", "rebuild_index": False},
        )

    assert "super-secret-token" not in str(exc_info.value.detail)
