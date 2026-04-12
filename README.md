# local-agent
 
 A personal local document agent — index local files and web pages into a knowledge base and query them via a ReAct loop powered by either a local Ollama model or Claude. Runs as either a terminal REPL or an MCP server wired into Claude Code.

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
| `connectors/web.py` | Fetches URLs (HTML pages + raw text, including GitHub file URLs) and extracts readable text |
| `connectors/memory.py` | Maintains a personal memo file (add/search/list/delete memos) at `MEMORY_FILE_PATH` |

### Tools (`tools/`)
| Module | What it does |
|---|---|
| `tools/registry_openai.py` | Tool schemas + dispatch for Ollama/OpenAI-compatible tool calling |
| `tools/registry_anthropic.py` | Tool schemas + dispatch for Anthropic/Claude tool calling |

### Entry points
| File | What it does |
|---|---|
| `agent.py` | Terminal REPL dispatcher — selects Ollama vs Anthropic based on `MODEL_TYPE` |
| `agent_ollama.py` | Terminal REPL implementation for Ollama models (default: `llama3.1:8b`) |
| `agent_anthropic.py` | Terminal REPL implementation for Anthropic models |
| `mcp_server.py` | MCP server — exposes the same 4 tools so Claude Code can call them directly without a separate session |

### Tools available in the Terminal REPL
| Tool | Description |
|---|---|
| `ingest_doc` | Index a local file or URL into the knowledge base (re-ingest is safe — old chunks are replaced) |
| `search_docs` | Semantic search over indexed documents, returns top-N chunks |
| `update_doc` | Write or append content to a local file |
| `list_docs` | Show all indexed documents with chunk counts |
| `add_memo` | Add a memo to your personal memory file |
| `search_memos` | Search through your memos |
| `list_memo_topics` | List all memo topics |
| `delete_memo` | Delete a memo by topic |

---

## Setup

### Prerequisites
- Python 3.11+
- Either:
  - Ollama running locally (recommended), or
  - An Anthropic API key

### Install

```bash
# Clone and enter the project
cd local-agent

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
python3 -m pip install -r requirements.txt
```

### Configure
 
Create a `.env` file in the project root:
 
```
# Choose the backend: "ollama" or "anthropic"
MODEL_TYPE=ollama
 
# Ollama settings
OLLAMA_MODEL=llama3.1:8b
 
# Anthropic settings (only needed if MODEL_TYPE=anthropic)
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-opus-4-6
 
# Optional: where memos are stored (defaults to ~/memory.md)
MEMORY_FILE_PATH=~/notes/memory.md
```

---

## Usage

### Option A — Terminal REPL
 
```bash
python3 agent.py
```

Type a goal in natural language. The agent will call tools in sequence until it has an answer.

```
You: Index my notes at ~/notes/meeting.md and summarize the key action items
```

You can also ingest URLs:
 
```
You: Ingest https://github.com/user/repo/blob/main/README.md and summarize what it does
```

And maintain personal memos:
 
```
You: Add a memo with topic "Onboarding" and content "Remember to update README when adding tools" with tags ["process"]
```

### Option B — MCP server (Claude Code)

The server is registered globally in `~/.claude.json`:

```json
"mcpServers": {
    "local-doc-agent": {
        "command": "python3",
        "args": ["/absolute/path/to/local-agent/mcp_server.py"]
    }
}
```

Once registered, Claude Code can call all tools directly in any conversation.

Notes:
- `ingest_doc` supports local files and URLs.

---

## Project structure

```
local-agent/
├── agent.py              # Terminal REPL dispatcher
├── agent_ollama.py        # Ollama agent implementation
├── agent_anthropic.py     # Anthropic agent implementation
├── mcp_server.py         # MCP server entry point
├── requirements.txt
├── .env                  # API key (not committed)
├── connectors/
│   ├── local.py          # Local file reader
│   ├── web.py            # URL fetch + extraction
│   └── memory.py         # Memo file management
├── rag/
│   ├── ingest.py         # Chunk + embed + store pipeline
│   ├── retrieve.py       # Semantic search
│   ├── embeddings.py     # sentence-transformers wrapper
│   └── store.py          # ChromaDB collection manager
└── tools/
    ├── registry_openai.py     # Tool schemas + dispatch for Ollama/OpenAI
    └── registry_anthropic.py  # Tool schemas + dispatch for Anthropic/Claude
```

---

## Planned additions
 
- [ ] **PDF / DOCX support** — extend `connectors/local.py` to parse binary document formats
- [ ] **Directory ingest** — bulk-index an entire folder with a single command
- [ ] **Conversation memory** — persist chat history across REPL sessions
- [ ] **Metadata filtering** — scope searches to a specific file, folder, or date range
- [ ] **Re-ranking** — add a cross-encoder re-rank step after retrieval for higher precision
- [ ] **Scheduled ingest** — watch directories and auto-reindex changed files
