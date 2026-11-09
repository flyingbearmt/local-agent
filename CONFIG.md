# Configuration Options

These options configure the terminal REPL, not the stdio MCP server. For MCP setup, see [README](README.md).

## Environment Variables

Create a `.env` file in the project root. See `.env.example` for a complete example.

### Model Selection
```bash
# Choose which model backend to use
MODEL_TYPE=ollama          # Options: "ollama" or "anthropic"

# For Ollama (local models)
OLLAMA_MODEL=llama3.1:8b   # Your local Ollama model name

# For Anthropic (Claude)
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-opus-4-6
```

### Memory Configuration
```bash
# Path to your memory file (optional, defaults to ~/memory.md)
MEMORY_FILE_PATH=~/notes/memory.md
```

### Examples

#### Using Local Ollama Model
```bash
MODEL_TYPE=ollama
OLLAMA_MODEL=llama3.1:8b
MEMORY_FILE_PATH=~/docs/memory.md
```

#### Using Claude
```bash
MODEL_TYPE=anthropic
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_MODEL=claude-opus-4-6
MEMORY_FILE_PATH=~/memory.md
```

## Registry Files

The agent automatically selects the appropriate tool registry based on `MODEL_TYPE`:

- `tools/registry_openai.py` - For Ollama/OpenAI-compatible models
- `tools/registry_anthropic.py` - For Anthropic/Claude models

Both files contain the same tools but with different API schemas.

## Memory Tool

The memory tool allows you to maintain a personal memo file with:
- Add memos with topics and tags
- Search through your memos
- List all memo topics
- Delete memos by topic

Default location: `~/memory.md` (unless overridden by `MEMORY_FILE_PATH`)
