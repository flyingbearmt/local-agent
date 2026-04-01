"""
MCP Server — Local Document Agent
==================================
Exposes the 4 RAG tools as MCP tools so Claude Code can call them
directly without a separate agent.py session.

Register this server in ~/.claude.json (see README or setup instructions).
"""

import os
import sys

# Make sure imports resolve when the server is launched from any directory
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from rag.ingest import ingest_document
from rag.retrieve import search_documents
from rag.store import get_collection

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

mcp = FastMCP("local-doc-agent")


@mcp.tool()
def ingest_doc(path: str) -> str:
    """
    Read a local file and index it into the knowledge base so it can be searched.
    Supports: .txt .md .py .json .yaml .yml .csv .rst
    Re-ingesting a file that was already indexed is safe — old chunks are replaced.
    """
    return ingest_document(path)


@mcp.tool()
def search_docs(query: str, n_results: int = 5) -> str:
    """
    Search the knowledge base for passages relevant to a query.
    Returns the most similar chunks with their source file and similarity score.
    Call this to answer questions about indexed documents or to gather context
    before writing/updating a file.
    """
    return search_documents(query, n_results)


@mcp.tool()
def update_doc(path: str, content: str, mode: str = "overwrite") -> str:
    """
    Write content to a local file.
    mode='overwrite' (default) replaces the entire file.
    mode='append' adds content to the end of the file.
    Parent directories are created automatically if they don't exist.
    """
    write_mode = "a" if mode == "append" else "w"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, write_mode, encoding="utf-8") as f:
        f.write(content)
    verb = "Appended to" if mode == "append" else "Wrote"
    return f"{verb} '{path}'."


@mcp.tool()
def list_docs() -> str:
    """
    List all documents currently indexed in the knowledge base,
    with chunk counts per file.
    """
    collection = get_collection()
    results = collection.get()
    if not results["ids"]:
        return "No documents indexed yet. Use ingest_doc to add files."

    sources: dict[str, int] = {}
    for meta in results["metadatas"]:
        if meta and "source" in meta:
            sources[meta["source"]] = sources.get(meta["source"], 0) + 1

    lines = [f"Indexed documents ({len(sources)} files, {len(results['ids'])} chunks total):"]
    for src in sorted(sources):
        lines.append(f"  - {src}  ({sources[src]} chunks)")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
