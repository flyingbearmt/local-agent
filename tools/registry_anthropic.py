import os
from rag.ingest import ingest_document
from rag.retrieve import search_documents
from rag.store import get_collection
from connectors.memory import add_memo, search_memos, list_memo_topics, delete_memo

# ── Tool definitions for Anthropic/Claude API ─────────────────────────────────
#
# Each entry tells Claude: here is a tool you can call, what it does, and what
# arguments it expects. Claude decides when and how to call them.

TOOL_DEFINITIONS = [
    {
        "name": "ingest_doc",
        "description": (
            "Read a local file or web page and index it into the knowledge base so it can be searched. "
            "Supports local files (.txt .md .py .json .yaml .yml .csv .rst) and web URLs (HTML pages, GitHub files). "
            "Call this when the user wants to add or re-index a document."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to local file, or full URL for web content.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_docs",
        "description": (
            "Search the knowledge base for chunks relevant to a query. "
            "Returns the most similar text passages with their source file and similarity score. "
            "Use this to answer questions or gather context before writing/updating a doc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."},
                "n_results": {
                    "type": "integer",
                    "description": "How many chunks to return (default 5).",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "update_doc",
        "description": (
            "Write content to a local file. Use mode='overwrite' to replace the file, "
            "or mode='append' to add to the end of it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to write."},
                "content": {"type": "string", "description": "Content to write."},
                "mode": {
                    "type": "string",
                    "enum": ["overwrite", "append"],
                    "description": "overwrite (default) replaces the file; append adds to it.",
                    "default": "overwrite",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "add_memo",
        "description": (
            "Add a memo to your personal memory file. "
            "Use this to save notes, ideas, reminders, or any information you want to keep. "
            "Each memo has a topic, content, and optional tags for organization."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The topic or title of the memo."},
                "content": {"type": "string", "description": "The content/body of the memo."},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of tags for categorization (e.g., ['work', 'idea', 'todo']).",
                    "default": []
                }
            },
            "required": ["topic", "content"],
        },
    },
    {
        "name": "search_memos",
        "description": (
            "Search through your memos for specific content. "
            "Returns all memos that contain your search query."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query to find in memos."},
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 10).",
                    "default": 10
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_memo_topics",
        "description": "List all memo topics in your memory file.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "delete_memo",
        "description": "Delete a memo by its topic. Be careful - this cannot be undone.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The exact topic of the memo to delete."}
            },
            "required": ["topic"],
        },
    },
    {
        "name": "list_docs",
        "description": "List all documents currently indexed in the knowledge base.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


# ── Tool handlers (the actual Python implementations) ────────────────────────

def _update_doc(path: str, content: str, mode: str = "overwrite") -> str:
    write_mode = "a" if mode == "append" else "w"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, write_mode, encoding="utf-8") as f:
        f.write(content)
    verb = "Appended to" if mode == "append" else "Wrote"
    return f"{verb} '{path}'."


def _list_docs() -> str:
    collection = get_collection()
    results = collection.get()
    if not results["ids"]:
        return "No documents indexed yet."

    sources: dict[str, int] = {}
    for meta in results["metadatas"]:
        if meta and "source" in meta:
            sources[meta["source"]] = sources.get(meta["source"], 0) + 1

    lines = [f"Indexed documents ({len(sources)} files, {len(results['ids'])} chunks total):"]
    for src in sorted(sources):
        lines.append(f"  - {src}  ({sources[src]} chunks)")
    return "\n".join(lines)


def execute_tool(name: str, inputs: dict) -> str:
    """Dispatch a tool call from the agent loop to the right handler."""
    try:
        if name == "ingest_doc":
            return ingest_document(inputs["path"])
        elif name == "search_docs":
            return search_documents(inputs["query"], inputs.get("n_results", 5))
        elif name == "update_doc":
            return _update_doc(inputs["path"], inputs["content"], inputs.get("mode", "overwrite"))
        elif name == "add_memo":
            return add_memo(inputs["topic"], inputs["content"], inputs.get("tags", []))
        elif name == "search_memos":
            return search_memos(inputs["query"], inputs.get("max_results", 10))
        elif name == "list_memo_topics":
            return list_memo_topics()
        elif name == "delete_memo":
            return delete_memo(inputs["topic"])
        elif name == "list_docs":
            return _list_docs()
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error in {name}: {e}"
