"""
MCP Server — Local Document Agent
==================================
Exposes personal documents, memos, and read-only team knowledge via stdio MCP.
"""

import os
import sys

# Make sure imports resolve when the server is launched from any directory
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP

from mcp_knowledge import (
    ingest_personal, list_documents, locked_state, private_path,
    search_documents, sync_team, update_personal,
)
from connectors.memory import add_memo, search_memos, list_memo_topics, delete_memo


def _check_memory_path() -> None:
    os.environ["MEMORY_FILE_PATH"] = str(private_path("memory.md"))

mcp = FastMCP("local-doc-agent")


@mcp.tool()
def ingest_doc(path: str) -> str:
    """
    Read a file inside LOCAL_AGENT_HOME/personal and index it as personal knowledge.
    Supports: .txt .md .py .json .yaml .yml .csv .rst
    Re-ingesting a file that was already indexed is safe — old chunks are replaced.
    """
    return ingest_personal(path)


@mcp.tool()
def search_docs(query: str, n_results: int = 5, scope: str = "personal") -> str:
    """
    Search personal, team, or all indexed documents (default: personal).
    Returns passages with scope, source file, and team Git blob version.
    Call this to answer questions about indexed documents or to gather context
    before writing/updating a file.
    """
    return search_documents(query, n_results, scope)


@mcp.tool()
def update_doc(path: str, content: str, mode: str = "overwrite") -> str:
    """
    Write content to a personal file inside LOCAL_AGENT_HOME/personal.
    mode='overwrite' (default) replaces the entire file.
    mode='append' adds content to the end of the file.
    Parent directories are created automatically if they don't exist.
    """
    return update_personal(path, content, mode)


@mcp.tool()
def list_docs(scope: str = "personal") -> str:
    """
    List indexed personal, team, or all documents with chunk counts.
    """
    return list_documents(scope)


@mcp.tool()
def sync_team_docs() -> str:
    """Sync committed Markdown in the team's agent-knowledge/knowledge/android/ Git tree.

    Only the local read-only index is changed; no path or ref argument is accepted.
    """
    return sync_team()


@mcp.tool()
def add_memo_tool(topic: str, content: str, tags: list[str] | None = None) -> str:
    """
    Add a memo to your personal memory file.
    topic: short title for the memo.
    content: body text.
    tags: optional list of tag strings for categorization.
    """
    with locked_state():
        _check_memory_path()
        return add_memo(topic, content, tags)


@mcp.tool()
def search_memos_tool(query: str, max_results: int = 10) -> str:
    """
    Search through your personal memos for a query string.
    Returns matching memo sections (up to max_results).
    """
    with locked_state():
        _check_memory_path()
        return search_memos(query, max_results)


@mcp.tool()
def list_memo_topics_tool() -> str:
    """
    List all memo topics currently stored in the memory file.
    """
    with locked_state():
        _check_memory_path()
        return list_memo_topics()


@mcp.tool()
def delete_memo_tool(topic: str) -> str:
    """
    Delete a memo by its exact topic title.
    """
    with locked_state():
        _check_memory_path()
        return delete_memo(topic)


if __name__ == "__main__":
    mcp.run()
