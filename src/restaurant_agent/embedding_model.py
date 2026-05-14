from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Protocol, cast

from restaurant_agent.config import get_settings


class SentenceEncoder(Protocol):
    def encode(self, *args: object, **kwargs: object) -> object: ...


@contextmanager
def _offline_hf_env() -> Iterator[None]:
    previous = {
        "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE"),
        "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE"),
    }
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def load_sentence_transformer(*, local_files_only: bool) -> SentenceEncoder:
    # type: ignore
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    model_name = "sentence-transformers/all-MiniLM-L6-v2"

    kwargs = {"cache_folder": settings.hf_home}
    if local_files_only:
        try:
            return cast(
                SentenceEncoder,
                SentenceTransformer(model_name, local_files_only=True, **kwargs),
            )
        except TypeError:
            with _offline_hf_env():
                return cast(SentenceEncoder, SentenceTransformer(model_name, **kwargs))

    return cast(SentenceEncoder, SentenceTransformer(model_name, **kwargs))
