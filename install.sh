#!/bin/bash
# Claude Code RAG - One-liner installer
# curl -fsSL https://raw.githubusercontent.com/tarpediem/claude-code-rag/main/install.sh | bash

set -e

echo "🧠 Installing Claude Code RAG..."

# Check for required tools
if ! command -v git &> /dev/null; then
    echo "❌ Error: git is required but not installed."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is required but not installed."
    exit 1
fi

# Install directory
INSTALL_DIR="${HOME}/.local/share/claude-code-rag"

# Clone repository
if [ -d "$INSTALL_DIR" ]; then
    echo "📦 Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "📦 Cloning repository..."
    git clone https://github.com/tarpediem/claude-code-rag.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Install with uv (preferred) or pip
if command -v uv &> /dev/null; then
    echo "📦 Installing with uv..."
    uv sync
else
    echo "📦 Installing with pip..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
fi

# Create symlink for CLI
mkdir -p "${HOME}/.local/bin"
ln -sf "${INSTALL_DIR}/.venv/bin/claude-rag" "${HOME}/.local/bin/claude-rag"

# Check for Ollama
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Warning: Ollama not found. Install from https://ollama.ai"
    echo "   Then run: ollama pull nomic-embed-text"
else
    echo "🤖 Pulling embedding model..."
    ollama pull nomic-embed-text || echo "⚠️  Failed to pull model, do it manually: ollama pull nomic-embed-text"
fi

# Add MCP server config (optional)
if [ -f "${HOME}/.claude.json" ]; then
    echo "🔌 MCP server configuration found at ~/.claude.json"
    echo "   Add this to mcpServers:"
    echo ""
    echo "    \"claude-rag\": {"
    echo "      \"command\": \"uv\","
    echo "      \"args\": [\"--directory\", \"${INSTALL_DIR}\", \"run\", \"python\", \"mcp_server.py\"]"
    echo "    }"
    echo ""
fi

# Initialize database
echo "🗄️  Initializing database..."
"${INSTALL_DIR}/.venv/bin/python" -m claude_rag init || true

echo ""
echo "✅ Installation complete!"
echo ""
echo "Usage:"
echo "  claude-rag index ~/your-docs/       # Index files"
echo "  claude-rag search \"your query\"       # Search memories"
echo "  claude-rag web                       # Launch Web UI"
echo "  claude-rag ui                        # Launch TUI"
echo ""
echo "🔧 Add ~/.local/bin to your PATH if not already:"
echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
echo "📖 Documentation: https://github.com/tarpediem/claude-code-rag"
