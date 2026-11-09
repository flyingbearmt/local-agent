# local-agent

A local document and memo agent. Run `agent.py` as a terminal REPL, or expose one stdio MCP server to both Claude Code and Codex. No remote memory service is required.

## Install

Requires Python 3.11+ and Git. From this checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Shared MCP setup

Both clients launch the **same** `mcp_server.py`. Replace the example absolute paths. Use the **same** `LOCAL_AGENT_HOME` outside any Git checkout in both configs. `TEAM_REPO_PATH` points to the root of your authorized local `android-cfx-tools` checkout; set `TEAM_GIT_REF` to its reviewed ref (for example `refs/remotes/origin/main`). This MCP does not read `.env` or need API keys.

Claude Code — merge into your user-local `~/.claude.json`:

```json
{
  "mcpServers": {
    "local-doc-agent": {
      "type": "stdio",
      "command": "/absolute/path/local-agent/.venv/bin/python",
      "args": ["/absolute/path/local-agent/mcp_server.py"],
      "env": {
        "LOCAL_AGENT_HOME": "/absolute/private/path/local-agent-data",
        "TEAM_REPO_PATH": "/absolute/path/android-cfx-tools",
        "TEAM_GIT_REF": "refs/remotes/origin/main"
      }
    }
  }
}
```

Codex CLI/desktop — add to your user-local `~/.codex/config.toml`:

```toml
[mcp_servers.local-doc-agent]
command = "/absolute/path/local-agent/.venv/bin/python"
args = ["/absolute/path/local-agent/mcp_server.py"]

[mcp_servers.local-doc-agent.env]
LOCAL_AGENT_HOME = "/absolute/private/path/local-agent-data"
TEAM_REPO_PATH = "/absolute/path/android-cfx-tools"
TEAM_GIT_REF = "refs/remotes/origin/main"
```

Check registration with `claude mcp list` and `codex mcp list`, then restart both clients to load the current MCP tools. To verify the setup:

1. Ask either client to call `list_docs(scope="all")`.
2. After updating the authorized team Git checkout, call `sync_team_docs()`, then `list_docs(scope="team")`. The scaffold has no topic documents, so an empty team result is expected until the first content PR merges.

If `sync_team_docs` is missing, check which MCP server the client loaded and restart it. First embedding/search may download the local sentence-transformers models. The MCP itself does not upload documents, but a client can send retrieved passages to its model provider.

## MCP tools and boundaries

- `update_doc(path, content, mode="overwrite")` and `ingest_doc(path)` write/read only supported files in `LOCAL_AGENT_HOME/personal/`; relative paths start there. URLs and paths or symlinks escaping this directory are rejected.
- `add_memo_tool`, `search_memos_tool`, `list_memo_topics_tool`, `delete_memo_tool` keep preferences in `LOCAL_AGENT_HOME/memory.md`, never in the team index or Git.
- `search_docs(query, n_results=5, scope="personal")` and `list_docs(scope="personal")` accept `personal`, `team`, or `all`. Results show source and, for team documents, the Git blob version.
- After your normal authorized Git update, call `sync_team_docs()` to index committed `.md`/`.markdown` files under `agent-knowledge/knowledge/android/` at `TEAM_GIT_REF`. The scaffold PR has no topic documents, so an empty team index is expected until a content PR merges. Only changed files are re-embedded; deleted files are removed. Uncommitted files, symlinks, and other paths are ignored. The tool accepts no path/ref override and never runs Git fetch/pull or writes to the checkout.

## Local notes and team publication

- The [Android team installation guide and Stop hook templates](https://github.com/pelotoncycle/android-cfx-tools/pull/7) live under `android-cfx-tools/agent-knowledge/`; the prompt text is in `agent-knowledge/install-templates/persist-learnings.prompt.md`. The Stop hook prompts Claude or Codex to save useful local learnings; the hook script itself never calls this MCP or writes to the team Git repository. This README covers MCP setup, not hook installation.
- The Android project's `.ai-work/codebase-map/` and the existing private `~/Documents/agent/memory/android/` are outside `LOCAL_AGENT_HOME/personal/`. To search a selected map file through MCP, copy it into `LOCAL_AGENT_HOME/personal/` with the author's approval, then call `ingest_doc` using a path relative to `personal/` (for example `codebase-map/INDEX.md`). Do not bulk-copy private notes. The hook's memory files and the MCP's `LOCAL_AGENT_HOME/memory.md` memos are separate stores; neither migrates nor syncs automatically.
- Sharing is a separate, author-initiated change to `agent-knowledge/knowledge/android/`, reviewed and merged through a PR. Only then does `sync_team_docs()` read the approved Git ref into each developer's local team index. Review and branch protection—not this MCP—determine what is approved. PR generation, personal-note sharing, and Hive integration are out of scope here.

## Recovery and legacy REPL

MCP state (`personal/`, `memory.md`, `chroma/`, `index.lock`) stays under `LOCAL_AGENT_HOME`, not this checkout. Two MCP processes serialize Chroma access with a file lock; do not point other Chroma clients directly at that directory. To rebuild a damaged index, stop both MCP processes, move `chroma/` to a private backup, restart, call `sync_team_docs()`, then re-ingest personal source files. Retrying a failed sync is safe; it reads Git before deleting stale entries.

Old MCP installations kept an index in `local-agent/store/` and memos in `~/memory.md`; neither is silently moved. Back up and copy the memos you want to keep to `LOCAL_AGENT_HOME/memory.md`, move personal source files under `LOCAL_AGENT_HOME/personal/`, and call `ingest_doc` again. Leave old data intact until you verify the new index.

The separate terminal REPL still runs with `.venv/bin/python agent.py` and supports Ollama or Anthropic via `.env` (see `.env.example`). Its older file/URL tools and store are **not** the scoped MCP index. For MCP tests, run `.venv/bin/python -m unittest discover -s tests -v`.
