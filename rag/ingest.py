import os
from connectors.local import read_local_file
from rag.embeddings import embed_texts
from rag.store import get_collection


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping word-based chunks.

    chunk_size: number of words per chunk
    overlap:    number of words shared between consecutive chunks
                (so context isn't lost at chunk boundaries)
    """
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def ingest_document(path: str) -> str:
    """
    Full ingest pipeline for a single file:
      1. Read  → raw text via connector
      2. Chunk → overlapping word windows
      3. Embed → sentence-transformers vectors
      4. Store → upsert into ChromaDB (re-ingest safe)
    """
    text = read_local_file(path)
    if not text.strip():
        return f"File is empty: {path}"

    chunks = chunk_text(text)
    embeddings = embed_texts(chunks)

    collection = get_collection()
    abs_path = os.path.abspath(path)

    # Remove stale chunks if the file was previously ingested
    existing = collection.get(where={"source": abs_path})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    ids = [f"{abs_path}::chunk_{i}" for i in range(len(chunks))]
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=[{"source": abs_path, "chunk_index": i} for i in range(len(chunks))],
    )

    return f"Ingested '{path}' — {len(chunks)} chunks stored."
