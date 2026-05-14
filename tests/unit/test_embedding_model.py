import sys
import types

from restaurant_agent.embedding_model import load_sentence_transformer


def test_load_sentence_transformer_retries_without_local_files_only(
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            calls.append({"model_name": model_name, **kwargs})
            if "local_files_only" in kwargs:
                raise TypeError("unexpected keyword argument 'local_files_only'")

    fake_module = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    monkeypatch.setenv("HF_HOME", ".cache/huggingface")

    model = load_sentence_transformer(local_files_only=True)

    assert isinstance(model, FakeSentenceTransformer)
    assert calls[0]["local_files_only"] is True
    assert "local_files_only" not in calls[1]
