import os
import chromadb

_client = None
_collection = None


def get_collection():
    """Return the ChromaDB collection, creating it if needed."""
    global _client, _collection
    if _collection is None:
        store_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "store")
        _client = chromadb.PersistentClient(path=store_path)
        _collection = _client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection
