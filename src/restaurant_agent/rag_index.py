import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Union, cast

import numpy as np
from restaurant_agent.config import get_settings
from restaurant_agent.menu_loader import load_menu
from restaurant_agent.schemas import CanonicalMenu

logger = logging.getLogger(__name__)


def build_menu_chunks(menu: CanonicalMenu) -> List[Dict[str, Any]]:
    chunks = []
    for item in menu.items:
        if not item.available:
            continue

        components = [
            f"Name: {item.name}",
            f"Category: {item.category}",
            f"Description: {item.description}",
        ]

        if item.aliases:
            components.append(f"Aliases: {', '.join(item.aliases)}")

        if item.ingredients:
            components.append(f"Ingredients: {', '.join(item.ingredients)}")

        if item.dietary_tags:
            components.append(f"Dietary: {', '.join(item.dietary_tags)}")

        if item.allergens:
            components.append(f"Allergens: {', '.join(item.allergens)}")

        if item.modifications:
            mods = [f"{m.name} (${m.price_delta:.2f})" for m in item.modifications]
            components.append(f"Modifications: {', '.join(mods)}")

        retrieval_text = "\n".join(components)

        chunk = {
            "chunk_id": f"chunk_{item.id}",
            "item_id": item.id,
            "item_name": item.name,
            "category": item.category,
            "description": item.description,
            "price": item.base_price,
            "retrieval_text": retrieval_text,
            "source_text": item.source_text,
        }
        chunks.append(chunk)

    return chunks


def build_rag_index(
    menu_path: Union[str, Path],
    index_dir: Union[str, Path],
    allow_embedding_failure: bool = True,
) -> Dict[str, Any]:
    menu = load_menu(menu_path)
    chunks = build_menu_chunks(menu)

    idx_dir = Path(index_dir)
    idx_dir.mkdir(parents=True, exist_ok=True)

    metadata: Dict[str, Any] = {
        "index_version": "1.0",
        "source_menu_path": str(menu_path),
        "embedding_model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "number_of_menu_items": len(menu.items),
        "number_of_chunks": len(chunks),
        "generated_timestamp": datetime.now(timezone.utc).isoformat(),
        "retrieval_modes_available": ["structured", "lexical"],
        "degraded_mode": True,
        "failure_reason": None,
    }

    try:
        # Try to import and load the sentence-transformers model
        # type: ignore
        from sentence_transformers import SentenceTransformer

        # Build only from a locally available embedding model. Reproduction can
        # pre-download it explicitly via `make download-models`.
        model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2",
            local_files_only=True,
        )
        texts = [chunk["retrieval_text"] for chunk in chunks]
        embeddings = model.encode(texts, show_progress_bar=False)

        np.save(idx_dir / "embeddings.npy", embeddings)
        metadata["retrieval_modes_available"].append("vector")
        metadata["retrieval_modes_available"].append("hybrid")
        metadata["degraded_mode"] = False
    except Exception as e:
        logger.warning(f"Failed to generate embeddings: {e}")
        metadata["failure_reason"] = str(e)
        if not allow_embedding_failure:
            raise RuntimeError(
                f"Embedding generation failed and allow_embedding_failure is False: {e}"
            ) from e

    with open(idx_dir / "menu_chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)

    with open(idx_dir / "menu_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def load_rag_metadata(index_dir: Union[str, Path]) -> Dict[str, Any]:
    meta_path = Path(index_dir) / "menu_metadata.json"
    if not meta_path.exists():
        return {}
    with open(meta_path, "r", encoding="utf-8") as f:
        return cast(Dict[str, Any], json.load(f))


def load_menu_chunks(index_dir: Union[str, Path]) -> List[Dict[str, Any]]:
    chunks_path = Path(index_dir) / "menu_chunks.json"
    if not chunks_path.exists():
        return []
    with open(chunks_path, "r", encoding="utf-8") as f:
        return cast(List[Dict[str, Any]], json.load(f))


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO)
    logger.info("Building RAG index...")
    try:
        metadata = build_rag_index(
            settings.menu_data_path,
            settings.menu_index_path,
            allow_embedding_failure=True,
        )
        logger.info(
            f"Index built successfully. Degraded mode: {metadata['degraded_mode']}"
        )
    except Exception as e:
        logger.error(f"Failed to build RAG index: {e}")
        import sys

        sys.exit(1)


if __name__ == "__main__":
    main()
