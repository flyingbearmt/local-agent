from sentence_transformers import SentenceTransformer, CrossEncoder

# Loaded once, reused for every embed call
_model = None
_reranker = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # all-MiniLM-L6-v2: small, fast, good quality — great for learning RAG
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        # Cross-encoder scores [query, chunk] jointly — slow, so only used to
        # re-order the shortlist, not the whole corpus.
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings, return list of float vectors."""
    model = get_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
