# local-agent

A personal local document agent — index local files into a knowledge base and query them via a ReAct loop powered by Claude. Runs as either a terminal REPL or an MCP server wired directly into Claude Code.

---

## What's included

### RAG pipeline (`rag/`)
| Module | What it does |
|---|---|
| `rag/ingest.py` | Reads a file, splits it into overlapping word-based chunks (500 words, 50-word overlap), embeds them, and upserts into ChromaDB |
| `rag/retrieve.py` | Embeds a query and returns the top-N most similar chunks with source file + similarity score |
| `rag/embeddings.py` | Wraps `sentence-transformers` to produce dense vectors |
| `rag/store.py` | Manages the persistent ChromaDB collection |

### Connectors (`connectors/`)
| Module | What it does |
|---|---|
| `connectors/local.py` | Reads local files; supported types: `.txt` `.md` `.py` `.json` `.yaml` `.yml` `.csv` `.rst` |

### Tools (`tools/`)
| Module | What it does |
|---|---|
| `tools/registry.py` | Defines the 4 tool schemas for the Anthropic API and dispatches calls to the right handler |

### Entry points
| File | What it does |
|---|---|
| `agent.py` | Terminal REPL — runs a ReAct loop (Reason → Act → Observe) using `claude-opus-4-6` |
| `mcp_server.py` | MCP server — exposes the same 4 tools so Claude Code can call them directly without a separate session |

### The 4 tools
| Tool | Description |
|---|---|
| `ingest_doc` | Index a local file into the knowledge base (re-ingest is safe — old chunks are replaced) |
| `search_docs` | Semantic search over indexed documents, returns top-N chunks |
| `update_doc` | Write or append content to a local file |
| `list_docs` | Show all indexed documents with chunk counts |

---

## Setup

### Prerequisites
- Python 3.11+
- An Anthropic API key

### Install

```bash
# Clone and enter the project
cd local-agent

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configure

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your_key_here
```

---

## Usage

### Option A — Terminal REPL

```bash
python agent.py
```

Type a goal in natural language. The agent will call tools in sequence until it has an answer.

```
You: Index my notes at ~/notes/meeting.md and summarize the key action items
```

### Option B — MCP server (Claude Code)

The server is registered globally in `~/.claude.json`:

```json
"mcpServers": {
    "local-doc-agent": {
        "command": "python",
        "args": ["/Users/tong.miao/Workspace/gadget/local-agent/mcp_server.py"]
    }
}
```

Once registered, Claude Code can call `ingest_doc`, `search_docs`, `update_doc`, and `list_docs` directly in any conversation.

---

## Project structure

```
local-agent/
├── agent.py              # Terminal REPL entry point
├── mcp_server.py         # MCP server entry point
├── requirements.txt
├── .env                  # API key (not committed)
├── connectors/
│   └── local.py          # Local file reader
├── rag/
│   ├── ingest.py         # Chunk + embed + store pipeline
│   ├── retrieve.py       # Semantic search
│   ├── embeddings.py     # sentence-transformers wrapper
│   └── store.py          # ChromaDB collection manager
└── tools/
    └── registry.py       # Tool schemas + dispatch for Anthropic API
```

---

## Planned additions

- [ ] **Web connector** — fetch and index URLs alongside local files
- [ ] **PDF / DOCX support** — extend `connectors/local.py` to parse binary document formats
- [ ] **Directory ingest** — bulk-index an entire folder with a single command
- [ ] **Conversation memory** — persist chat history across REPL sessions
- [ ] **Metadata filtering** — scope searches to a specific file, folder, or date range
- [ ] **Re-ranking** — add a cross-encoder re-rank step after retrieval for higher precision
- [ ] **Scheduled ingest** — watch directories and auto-reindex changed files
