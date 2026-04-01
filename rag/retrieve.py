from rag.embeddings import embed_query
from rag.store import get_collection


def search_documents(query: str, n_results: int = 5) -> str:
    """
    RAG retrieval step:
      1. Embed the query
      2. Run cosine similarity search in ChromaDB
      3. Return formatted chunks with source + score

    The returned string is injected directly into Claude's context window
    as the "retrieved knowledge" for generation.
    """
    collection = get_collection()

    count = collection.count()
    if count == 0:
        return "No documents indexed yet. Use ingest_doc first."

    query_embedding = embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, count),
        include=["documents", "metadatas", "distances"],
    )

    if not results["documents"][0]:
        return "No relevant documents found."

    output = []
    for i, (doc, meta, dist) in enumerate(
        zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
    ):
        source = meta.get("source", "unknown") if meta else "unknown"
        similarity = 1 - dist  # ChromaDB cosine distance → similarity
        output.append(f"[{i + 1}] {source}  (similarity: {similarity:.2f})\n{doc}")

    return "\n\n---\n\n".join(output)
