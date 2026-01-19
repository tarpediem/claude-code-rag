# 🚀 Claude Code Installation Prompt

Copy this prompt and paste it into Claude Code to automatically install **Claude Code RAG** on any platform:

```
Please install Claude Code RAG for me. Adapt the installation for my operating system:

1. Clone https://github.com/tarpediem/claude-code-rag to the appropriate location:
   - Linux: ~/.local/share/claude-code-rag
   - macOS: ~/Library/Application Support/claude-code-rag
   - Windows: %LOCALAPPDATA%\claude-code-rag

2. Install dependencies using uv (preferred) or pip
3. Create a CLI launcher appropriate for my OS
4. Pull the nomic-embed-text model with ollama (if installed)
5. Initialize the database
6. Show me how to configure the MCP server in ~/.claude.json

Repository: https://github.com/tarpediem/claude-code-rag

After installation, show me how to use it.
```

---

## Alternative: One-Liner Installation

### Linux / macOS
```bash
curl -fsSL https://raw.githubusercontent.com/tarpediem/claude-code-rag/main/install.sh | bash
```

### Windows (PowerShell as Administrator)
```powershell
iwr -useb https://raw.githubusercontent.com/tarpediem/claude-code-rag/main/install.ps1 | iex
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

**Linux / macOS:**
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

**Windows (PowerShell):**
```powershell
# Index your documentation
claude-rag index C:\projects\my-app\docs

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
