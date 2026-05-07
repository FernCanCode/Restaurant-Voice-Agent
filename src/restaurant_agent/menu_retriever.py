from pathlib import Path
from typing import List, Union, Dict

import numpy as np
from rapidfuzz import fuzz, process

from restaurant_agent.rag_index import load_menu_chunks, load_rag_metadata
from restaurant_agent.schemas import CanonicalMenu, MenuSearchResult


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

        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
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
