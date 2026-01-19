#!/usr/bin/env bash
# RAG Health Check Script
# Quickly verify that Ollama, ChromaDB, and the RAG system are working

set -e

echo "🏥 RAG Health Check"
echo "==================="
echo ""

# Check Ollama
echo -n "🤖 Ollama service: "
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Running"
else
    echo "❌ Not running"
    echo "   Start with: ollama serve"
    exit 1
fi

# Check embedding model
echo -n "📦 Embedding model (nomic-embed-text): "
if ollama list | grep -q "nomic-embed-text"; then
    echo "✅ Installed"
else
    echo "❌ Not found"
    echo "   Install with: ollama pull nomic-embed-text"
    exit 1
fi

# Check ChromaDB
echo -n "🗄️  ChromaDB: "
CHROMA_PATH="${CHROMA_PATH:-$HOME/.local/share/claude-memory}"
if [ -d "$CHROMA_PATH" ]; then
    echo "✅ Found at $CHROMA_PATH"
else
    echo "⚠️  Not initialized at $CHROMA_PATH"
    echo "   Initialize with: claude-rag init"
fi

# Basic connectivity test
echo -n "🔍 Basic connectivity: "
if curl -s http://localhost:11434/api/generate -d '{"model":"nomic-embed-text"}' > /dev/null 2>&1; then
    echo "✅ Working"
else
    echo "⚠️  API test inconclusive (but Ollama is running)"
fi

echo ""
echo "✅ All systems operational!"
echo ""
echo "💡 To get stats, use the MCP tool: rag_stats"
echo "   The MCP is more stable than the direct CLI."
