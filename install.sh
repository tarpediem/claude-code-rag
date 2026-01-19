#!/usr/bin/env bash
# Claude Code RAG - Cross-platform installer for Linux/macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/tarpediem/claude-code-rag/main/install.sh | bash

set -e

echo "🧠 Installing Claude Code RAG..."

# Detect OS
OS="$(uname -s)"
case "$OS" in
    Linux*)     OS_TYPE="Linux";;
    Darwin*)    OS_TYPE="macOS";;
    *)          echo "❌ Unsupported OS: $OS"; exit 1;;
esac
echo "📍 Detected OS: $OS_TYPE"

# Check for required tools
if ! command -v git &> /dev/null; then
    echo "❌ Error: git is required but not installed."
    echo "   macOS: xcode-select --install"
    echo "   Linux: sudo apt install git  or  sudo pacman -S git"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is required but not installed."
    echo "   macOS: brew install python3"
    echo "   Linux: sudo apt install python3  or  sudo pacman -S python"
    exit 1
fi

# Install directory (cross-platform)
if [ "$OS_TYPE" = "macOS" ]; then
    INSTALL_DIR="${HOME}/Library/Application Support/claude-code-rag"
    BIN_DIR="${HOME}/.local/bin"
else
    INSTALL_DIR="${HOME}/.local/share/claude-code-rag"
    BIN_DIR="${HOME}/.local/bin"
fi

# Clone repository
if [ -d "$INSTALL_DIR" ]; then
    echo "📦 Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "📦 Cloning repository..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
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

    # Activate venv (cross-platform)
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    else
        echo "❌ Failed to create virtual environment"
        exit 1
    fi

    pip install --upgrade pip
    pip install -e .
fi

# Create CLI launcher
mkdir -p "$BIN_DIR"

# Create wrapper script instead of symlink (more portable)
cat > "$BIN_DIR/claude-rag" << 'EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$OS_TYPE" = "macOS" ]; then
    RAG_DIR="${HOME}/Library/Application Support/claude-code-rag"
else
    RAG_DIR="${HOME}/.local/share/claude-code-rag"
fi
exec "${RAG_DIR}/.venv/bin/python" -m claude_rag "$@"
EOF
chmod +x "$BIN_DIR/claude-rag"

echo "✅ CLI installed at $BIN_DIR/claude-rag"

# Check for Ollama
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama not found. Install from https://ollama.ai"
    echo "   macOS: brew install ollama"
    echo "   Linux: curl https://ollama.ai/install.sh | sh"
    echo ""
    echo "   After installing, run: ollama pull nomic-embed-text"
else
    echo "🤖 Pulling embedding model..."
    ollama pull nomic-embed-text || echo "⚠️  Failed to pull model, run manually: ollama pull nomic-embed-text"
fi

# Add MCP server config (optional)
if [ -f "${HOME}/.claude.json" ]; then
    echo ""
    echo "🔌 Found ~/.claude.json - Add this MCP server config:"
    echo ""
    echo "  \"claude-rag\": {"
    echo "    \"command\": \"uv\","
    echo "    \"args\": ["
    echo "      \"--directory\", \"${INSTALL_DIR}\","
    echo "      \"run\", \"python\", \"mcp_server.py\""
    echo "    ]"
    echo "  }"
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

# PATH check
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "⚠️  Add $BIN_DIR to your PATH:"
    if [ "$OS_TYPE" = "macOS" ]; then
        echo "   echo 'export PATH=\"$BIN_DIR:\$PATH\"' >> ~/.zshrc"
        echo "   source ~/.zshrc"
    else
        echo "   echo 'export PATH=\"$BIN_DIR:\$PATH\"' >> ~/.bashrc"
        echo "   source ~/.bashrc"
    fi
    echo ""
fi

echo "📖 Documentation: https://github.com/tarpediem/claude-code-rag"
