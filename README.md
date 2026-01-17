# Claude Code RAG

> **Give Claude Code a persistent memory** - Local semantic search powered by Ollama + ChromaDB

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

![Demo](assets/demo.gif)

## Why?

Claude Code forgets everything between sessions. Your `CLAUDE.md` file grows, but searching it sucks.

**claude-code-rag** gives Claude Code a semantic memory:
- Index your docs, configs, and code
- Search by meaning, not keywords
- Remember decisions, bugfixes, and architecture choices
- 100% local - no cloud, no API keys

## Features

- **Semantic search** - Find relevant context even with different wording
- **Smart chunking** - Splits markdown by headers, Python by functions, JS by exports
- **Multi-format** - `.md`, `.txt`, `.py`, `.js`, `.ts`, `.json`, `.yaml`, `.sh`, `.toml`
- **Memory types** - Tag memories as `decision`, `bugfix`, `architecture`, `snippet`...
- **MCP integration** - Native Claude Code tools, no bash needed
- **Fast** - ~30ms search, ~1s/file indexing on AMD iGPU

## Quick Start

```bash
# 1. Clone
git clone https://github.com/tarpediem/claude-code-rag.git
cd claude-code-rag

# 2. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Pull embedding model
ollama pull nomic-embed-text

# 4. Test it
python claude_rag.py index ~/CLAUDE.md
python claude_rag.py search "how to configure GPU"
```

## MCP Integration (Recommended)

Add to `~/.claude.json` under your project:

```json
{
  "mcpServers": {
    "claude-rag": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/mcp_server.py"]
    }
  }
}
```

Restart Claude Code. You now have 5 native tools:

| Tool | Description |
|------|-------------|
| `rag_search` | Semantic search in memory |
| `rag_index` | Index files or directories |
| `rag_store` | Manually store a memory with type/tags |
| `rag_stats` | Show memory statistics |
| `rag_health` | Check Ollama/ChromaDB status |

## Usage Examples

### Index your codebase
```bash
# Single file
python claude_rag.py index ~/CLAUDE.md

# Entire directory (all supported formats)
python claude_rag.py index ~/myproject/
```

### Search
```bash
python claude_rag.py search "database connection error"
python claude_rag.py search "how to deploy"
```

### Store a decision (MCP)
```
Claude, store this: "We chose PostgreSQL over MongoDB for ACID compliance"
→ rag_store(content="...", memory_type="decision", tags=["database"])
```

### Check health
```bash
python claude_rag.py stats
# Or via MCP: rag_health
```

## Supported File Types

| Extension | Chunking Strategy |
|-----------|-------------------|
| `.md` | Split by `##` headers |
| `.py` | Split by `def`/`class` |
| `.js`, `.ts` | Split by `function`/`const`/`export` |
| `.json`, `.yaml`, `.toml` | Generic with overlap |
| `.txt`, `.sh` | Generic with overlap |

## Configuration

| Env Variable | Default | Description |
|--------------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `CHROMA_PATH` | `~/.local/share/claude-memory` | Database path |

## Performance

Tested on AMD Radeon 890M (integrated GPU) with ROCm:

| Operation | Speed |
|-----------|-------|
| Search | ~30ms |
| Index | ~1s/file |
| Embedding | ~100 tok/s |

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features:
- [ ] Auto-capture from Claude Code sessions
- [ ] Export memories to CLAUDE.md
- [ ] Web UI dashboard
- [ ] PyPI package

## Contributing

PRs welcome! Check the roadmap for ideas.

## License

MIT

---

**Built for the [Claude Code](https://claude.ai/code) community**
