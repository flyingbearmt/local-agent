from rank_bm25 import BM25Okapi
from rag.store import get_collection

_bm25 = None
_ids: list[str] = []
_docs: list[str] = []
_metas: list[dict] = []
_indexed_count = -1


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def _ensure_index():
    """(Re)build the BM25 index over stored chunks when the corpus changes."""
    global _bm25, _ids, _docs, _metas, _indexed_count
    collection = get_collection()
    count = collection.count()
    if _bm25 is not None and count == _indexed_count:
        return

    result = collection.get(include=["documents", "metadatas"])
    _ids = result["ids"]
    _docs = result["documents"]
    _metas = result["metadatas"]
    _bm25 = BM25Okapi([_tokenize(d) for d in _docs]) if _docs else None
    _indexed_count = count


def bm25_search(query: str, n: int) -> list[tuple[str, str, dict]]:
    """Return top-n (id, document, metadata) tuples by BM25 score."""
    _ensure_index()
    if _bm25 is None:
        return []

    scores = _bm25.get_scores(_tokenize(query))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [(_ids[i], _docs[i], _metas[i]) for i in ranked[:n] if scores[i] > 0]
