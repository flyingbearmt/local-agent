from sentence_transformers import SentenceTransformer

# Loaded once, reused for every embed call
_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # all-MiniLM-L6-v2: small, fast, good quality — great for learning RAG
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings, return list of float vectors."""
    model = get_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
