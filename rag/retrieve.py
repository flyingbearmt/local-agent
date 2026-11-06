from rag.embeddings import embed_query
from rag.store import get_collection
from rag.lexical import bm25_search
from rag.rerank import reciprocal_rank_fusion, rerank

CANDIDATE_POOL = 25


def _dense_search(query: str, n: int, count: int) -> list[tuple[str, str, dict]]:
    query_embedding = embed_query(query)
    results = get_collection().query(
        query_embeddings=[query_embedding],
        n_results=min(n, count),
        include=["documents", "metadatas"],
    )
    return list(
        zip(results["ids"][0], results["documents"][0], results["metadatas"][0])
    )


def search_documents(query: str, n_results: int = 5) -> str:
    """
    Hybrid RAG retrieval:
      1. Dense (cosine) + BM25 (lexical) each retrieve a wide candidate pool
      2. Reciprocal Rank Fusion merges the two ranked lists
      3. Cross-encoder reranks the fused pool, keeping the top n_results
      4. Format with a summary header + source/relevance per chunk

    The returned string is injected directly into the model's context as the
    "retrieved knowledge" — its first line also confirms to the user what was found.
    """
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return "No documents indexed yet. Use ingest_doc first."

    dense_hits = _dense_search(query, CANDIDATE_POOL, count)
    bm25_hits = bm25_search(query, CANDIDATE_POOL)

    fused = reciprocal_rank_fusion(dense_hits, bm25_hits)
    if not fused:
        return "No relevant documents found."

    top = rerank(query, fused, n_results)

    sources = {meta.get("source", "unknown") if meta else "unknown" for _, _, meta, _ in top}
    header = (
        f"Retrieved {len(top)} passage(s) from {len(sources)} source(s) "
        f"(searched {count} indexed chunks).\n"
    )

    output = [header]
    for i, (_, doc, meta, score) in enumerate(top):
        source = meta.get("source", "unknown") if meta else "unknown"
        output.append(f"[{i + 1}] {source}  (relevance: {score:.2f})\n{doc}")

    return "\n\n---\n\n".join(output)
