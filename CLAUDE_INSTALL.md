# 🚀 Claude Code Installation Prompt

Copy this prompt and paste it into Claude Code to automatically install **Claude Code RAG**:

```
Please install Claude Code RAG for me:

1. Clone the repository to ~/.local/share/claude-code-rag
2. Install dependencies using uv (or pip if uv not available)
3. Create a symlink for the CLI at ~/.local/bin/claude-rag
4. Pull the nomic-embed-text model with ollama (if ollama is installed)
5. Initialize the database
6. Add the MCP server configuration to my ~/.claude.json

Repository: https://github.com/tarpediem/claude-code-rag

After installation, show me how to:
- Index my first directory
- Search memories
- Launch the Web UI
```

---

## Alternative: One-Liner Installation

If you prefer a one-liner, run this in your terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/tarpediem/claude-code-rag/main/install.sh | bash
```

---

## Manual Installation

<details>
<summary>Click to expand manual steps</summary>

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.ai) installed and running
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tarpediem/claude-code-rag.git
   cd claude-code-rag
   ```

2. **Install dependencies:**
   ```bash
   # With uv (recommended)
   uv sync

   # Or with pip
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .
   ```

3. **Pull the embedding model:**
   ```bash
   ollama pull nomic-embed-text
   ```

4. **Initialize and test:**
   ```bash
   claude-rag init
   claude-rag index ~/your-docs/
   claude-rag search "how to configure something"
   ```

5. **(Optional) Add MCP server:**

   Add this to your `~/.claude.json`:
   ```json
   {
     "mcpServers": {
       "claude-rag": {
         "command": "uv",
         "args": [
           "--directory",
           "/absolute/path/to/claude-code-rag",
           "run",
           "python",
           "mcp_server.py"
         ]
       }
     }
   }
   ```

</details>

---

## Quick Start After Installation

```bash
# Index your documentation
claude-rag index ~/projects/my-app/docs/

# Search memories
claude-rag search "database configuration"

# Launch Web UI
claude-rag web

# Launch TUI
claude-rag ui
```

---

## Troubleshooting

**Ollama not responding:**
```bash
# Check if Ollama is running
ollama list

# Start Ollama (if needed)
ollama serve
```

**Model not found:**
```bash
ollama pull nomic-embed-text
```

**Command not found:**
```bash
# Add to your PATH
export PATH="$HOME/.local/bin:$PATH"

# Make permanent (add to ~/.bashrc, ~/.zshrc, or ~/.config/fish/config.fish)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```
