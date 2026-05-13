import re
from pathlib import Path
from typing import Dict, List, Union

import numpy as np
from rapidfuzz import fuzz, process

from restaurant_agent.rag_index import load_menu_chunks, load_rag_metadata
from restaurant_agent.schemas import CanonicalMenu, MenuSearchResult


_GENERIC_CATEGORY_WORDS = {
    "what",
    "which",
    "do",
    "you",
    "have",
    "show",
    "me",
    "options",
    "option",
    "available",
    "are",
    "is",
    "the",
    "menu",
    "please",
}

_DIETARY_TAGS = {"vegetarian", "vegan"}
_DRINK_ITEM_IDS = {"lemonade", "horchata"}


def _tokenize_query(query: str) -> List[str]:
    return re.findall(r"[a-z]+", query.lower())


def is_explicit_taco_category_query(query: str) -> bool:
    tokens = _tokenize_query(query)
    if not tokens or not any(token in {"taco", "tacos"} for token in tokens):
        return False

    filtered = [token for token in tokens if token not in _GENERIC_CATEGORY_WORDS]
    return bool(filtered) and set(filtered).issubset({"taco", "tacos"})


def _filter_taco_category(menu: CanonicalMenu) -> List[MenuSearchResult]:
    results: List[MenuSearchResult] = []
    for item in menu.items:
        if not item.available:
            continue

        category = item.category.strip().lower()
        item_name = item.name.strip().lower()
        if category == "tacos" or "taco" in item_name:
            results.append(
                MenuSearchResult(
                    item_id=item.id,
                    name=item.name,
                    category=item.category,
                    description=item.description,
                    price=item.base_price,
                    score=0.95,
                    source_text=item.source_text,
                )
            )

    return sorted(results, key=lambda item: item.name)


def explicit_dietary_tag_query(query: str) -> str | None:
    tokens = _tokenize_query(query)
    for dietary_tag in sorted(_DIETARY_TAGS):
        if dietary_tag in tokens:
            return dietary_tag
    return None


def explicit_collection_query(query: str) -> str | None:
    tokens = _tokenize_query(query)
    token_set = set(tokens)

    if is_explicit_taco_category_query(query):
        return "tacos"

    dietary_tag = explicit_dietary_tag_query(query)
    if dietary_tag:
        return dietary_tag

    if "drink" in token_set or "drinks" in token_set:
        return "drinks"

    if "meat" in token_set or "protein" in token_set or "proteins" in token_set:
        return "meat"

    if "side" in token_set or "sides" in token_set:
        return "sides"

    return None


def _filter_dietary_tag(
    menu: CanonicalMenu, dietary_tag: str
) -> List[MenuSearchResult]:
    normalized_tag = dietary_tag.strip().lower()
    results: List[MenuSearchResult] = []
    for item in menu.items:
        if not item.available:
            continue

        if any(normalized_tag == tag.strip().lower() for tag in item.dietary_tags):
            results.append(
                MenuSearchResult(
                    item_id=item.id,
                    name=item.name,
                    category=item.category,
                    description=item.description,
                    price=item.base_price,
                    score=0.9,
                    source_text=item.source_text,
                )
            )

    return sorted(results, key=lambda item: item.name)


def _filter_drinks(menu: CanonicalMenu) -> List[MenuSearchResult]:
    results: List[MenuSearchResult] = []
    for item in menu.items:
        if not item.available or item.id not in _DRINK_ITEM_IDS:
            continue
        results.append(
            MenuSearchResult(
                item_id=item.id,
                name=item.name,
                category=item.category,
                description=item.description,
                price=item.base_price,
                score=0.9,
                source_text=item.source_text,
            )
        )
    return sorted(results, key=lambda item: item.name)


def _filter_meat_options(menu: CanonicalMenu) -> List[MenuSearchResult]:
    results: List[MenuSearchResult] = []
    for item in menu.items:
        if not item.available:
            continue

        normalized_category = item.category.strip().lower()
        normalized_tags = {tag.strip().lower() for tag in item.dietary_tags}
        if normalized_category == "sides & drinks":
            continue
        if {"vegetarian", "vegan"} & normalized_tags:
            continue

        results.append(
            MenuSearchResult(
                item_id=item.id,
                name=item.name,
                category=item.category,
                description=item.description,
                price=item.base_price,
                score=0.9,
                source_text=item.source_text,
            )
        )
    return sorted(results, key=lambda item: item.name)


def _filter_sides(menu: CanonicalMenu) -> List[MenuSearchResult]:
    results: List[MenuSearchResult] = []
    for item in menu.items:
        if not item.available:
            continue
        if item.id in _DRINK_ITEM_IDS:
            continue
        if item.category.strip().lower() != "sides & drinks":
            continue
        results.append(
            MenuSearchResult(
                item_id=item.id,
                name=item.name,
                category=item.category,
                description=item.description,
                price=item.base_price,
                score=0.88,
                source_text=item.source_text,
            )
        )
    return sorted(results, key=lambda item: item.name)


def structured_filter_menu(query: str, menu: CanonicalMenu) -> List[MenuSearchResult]:
    results = []
    q = query.lower()
    for item in menu.items:
        if not item.available:
            continue

        # Simple structured match: exact category or substring in name
        if q in item.category.lower() or q in item.name.lower():
            results.append(
                MenuSearchResult(
                    item_id=item.id,
                    name=item.name,
                    category=item.category,
                    description=item.description,
                    price=item.base_price,
                    score=0.8,
                    source_text=item.source_text,
                )
            )
    return results


def lexical_search_menu(
    query: str, menu: CanonicalMenu, top_k: int = 5
) -> List[MenuSearchResult]:
    choices = {
        item.id: f"{item.name} {item.description} {' '.join(item.aliases)} {item.category}"
        for item in menu.items
        if item.available
    }
    if not choices:
        return []

    # Use rapidfuzz to find best matches
    extracted = process.extract(query, choices, scorer=fuzz.WRatio, limit=top_k)

    results = []
    for match in extracted:
        score = match[1] / 100.0  # normalize 0-1
        item_id = match[2]

        # If score is very low, it's just noise, skip
        if score < 0.4:
            continue

        item = next(i for i in menu.items if i.id == item_id)
        results.append(
            MenuSearchResult(
                item_id=item.id,
                name=item.name,
                category=item.category,
                description=item.description,
                price=item.base_price,
                score=score,
                source_text=item.source_text,
            )
        )
    return results


def vector_search_menu(
    query: str, index_dir: Union[str, Path], top_k: int = 5
) -> List[MenuSearchResult]:
    idx_dir = Path(index_dir)
    embeddings_path = idx_dir / "embeddings.npy"
    if not embeddings_path.exists():
        return []

    try:
        # type: ignore
        from sentence_transformers import SentenceTransformer

        # Never trigger a model download during request handling. If the model
        # is not already present locally, degrade to lexical/structured search.
        model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2",
            local_files_only=True,
        )
        query_emb = model.encode(query, show_progress_bar=False)

        doc_embs = np.load(embeddings_path)
        chunks = load_menu_chunks(idx_dir)

        if not chunks or len(chunks) != len(doc_embs):
            return []

        # Cosine similarity
        norm_query = np.linalg.norm(query_emb)
        norm_docs = np.linalg.norm(doc_embs, axis=1)
        sims = np.dot(doc_embs, query_emb) / (norm_docs * norm_query + 1e-9)

        top_indices = np.argsort(sims)[::-1][:top_k]

        results = []
        for i in top_indices:
            score = float(sims[i])
            if score < 0.2:
                continue
            chunk = chunks[i]
            results.append(
                MenuSearchResult(
                    item_id=chunk["item_id"],
                    name=chunk["item_name"],
                    category=chunk["category"],
                    description=chunk.get("description", ""),
                    price=float(chunk.get("price", 0.0)),
                    score=score,
                    source_text=chunk["source_text"],
                )
            )
        return results
    except Exception:
        # Failsafe: if sentence-transformers crashes, degrade gracefully
        return []


def search_menu(
    query: str,
    menu: CanonicalMenu,
    index_dir: Union[str, Path],
    top_k: int = 5,
) -> List[MenuSearchResult]:
    collection_query = explicit_collection_query(query)
    if collection_query == "tacos":
        return _filter_taco_category(menu)[:top_k]
    if collection_query in _DIETARY_TAGS:
        return _filter_dietary_tag(menu, collection_query)[:top_k]
    if collection_query == "drinks":
        return _filter_drinks(menu)[:top_k]
    if collection_query == "meat":
        return _filter_meat_options(menu)[:top_k]
    if collection_query == "sides":
        return _filter_sides(menu)[:top_k]

    meta = load_rag_metadata(index_dir)
    degraded = meta.get("degraded_mode", True)

    vector_results = []
    if not degraded:
        vector_results = vector_search_menu(query, index_dir, top_k=top_k)

    lexical_results = lexical_search_menu(query, menu, top_k=top_k)
    structured_results = structured_filter_menu(query, menu)

    # Combine and deduplicate, keeping best score
    seen: Dict[str, MenuSearchResult] = {}

    # Priority weighting can be done here, but simple max score works
    all_results = vector_results + lexical_results + structured_results

    for r in all_results:
        if r.item_id not in seen or r.score > seen[r.item_id].score:
            seen[r.item_id] = r

    final_results = sorted(seen.values(), key=lambda x: x.score, reverse=True)
    return final_results[:top_k]
