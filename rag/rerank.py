from rag.embeddings import get_reranker


def reciprocal_rank_fusion(
    dense_hits: list[tuple[str, str, dict]],
    bm25_hits: list[tuple[str, str, dict]],
    k: int = 60,
) -> list[tuple[str, str, dict]]:
    """
    Merge two ranked lists by Reciprocal Rank Fusion: score = sum(1 / (k + rank)).
    RRF needs no score normalization, so cosine and BM25 ranks combine cleanly.
    """
    scores: dict[str, float] = {}
    payload: dict[str, tuple[str, str, dict]] = {}

    for hits in (dense_hits, bm25_hits):
        for rank, (chunk_id, doc, meta) in enumerate(hits):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            payload[chunk_id] = (chunk_id, doc, meta)

    fused_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    return [payload[cid] for cid in fused_ids]


def rerank(
    query: str,
    candidates: list[tuple[str, str, dict]],
    top_n: int,
) -> list[tuple[str, str, dict, float]]:
    """Score [query, chunk] pairs with the cross-encoder, return top_n with score."""
    if not candidates:
        return []

    reranker = get_reranker()
    pairs = [[query, doc] for _, doc, _ in candidates]
    scores = reranker.predict(pairs)

    ranked = sorted(
        zip(candidates, scores), key=lambda x: x[1], reverse=True
    )
    return [(cid, doc, meta, float(score)) for (cid, doc, meta), score in ranked[:top_n]]
