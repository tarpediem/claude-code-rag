#!/usr/bin/env python3
"""
Claude Code RAG - CLI Tool
Semantic memory for Claude Code with Ollama embeddings + ChromaDB
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import chromadb
import requests

# Configuration
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
CHROMA_PATH = os.environ.get("CHROMA_PATH", os.path.expanduser("~/.local/share/claude-memory"))
MCP_SERVER = Path(__file__).parent / "mcp_server.py"
VENV_PYTHON = Path(__file__).parent / ".venv" / "bin" / "python"


def get_embedding(text: str) -> list:
    """Get embedding from Ollama"""
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=30
    )
    return resp.json()["embedding"]


class SimpleRAG:
    def __init__(self, collection_name: str = "claude_memory"):
        os.makedirs(CHROMA_PATH, exist_ok=True)
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_document(self, filepath: str, chunk_size: int = 500):
        """Index a document"""
        path = Path(filepath)
        content = path.read_text()
        doc_id = hashlib.md5(filepath.encode()).hexdigest()[:8]

        # Simple chunking
        chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]

        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        embeddings = [get_embedding(c) for c in chunks]
        metadatas = [{"source": filepath, "chunk": i} for i in range(len(chunks))]

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )
        return len(chunks)

    def search(self, query: str, n_results: int = 3) -> list:
        """Search for relevant chunks"""
        query_embedding = get_embedding(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        return [
            {"text": doc, "source": meta["source"], "score": 1-dist}
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            )
        ]

    def stats(self):
        """Get collection stats"""
        return {
            "total_chunks": self.collection.count(),
            "path": CHROMA_PATH
        }


# =============================================================================
# CLI Commands
# =============================================================================

def cmd_init(args):
    """Initialize claude-rag: check deps, pull model, create DB"""
    print("🚀 Initializing claude-rag...\n")

    # 1. Check Ollama
    print("1. Checking Ollama...")
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            print(f"   ✅ Ollama running at {OLLAMA_URL}")
        else:
            print(f"   ❌ Ollama not responding")
            return 1
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Ollama not running. Start with: systemctl start ollama")
        return 1

    # 2. Check/pull embedding model
    print(f"\n2. Checking embedding model ({EMBED_MODEL})...")
    models = [m["name"] for m in resp.json().get("models", [])]
    if any(EMBED_MODEL in m for m in models):
        print(f"   ✅ Model {EMBED_MODEL} available")
    else:
        print(f"   ⏳ Pulling {EMBED_MODEL}...")
        result = subprocess.run(["ollama", "pull", EMBED_MODEL], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✅ Model {EMBED_MODEL} pulled")
        else:
            print(f"   ❌ Failed to pull model: {result.stderr}")
            return 1

    # 3. Create DB directory
    print(f"\n3. Setting up database...")
    os.makedirs(CHROMA_PATH, exist_ok=True)
    print(f"   ✅ Database path: {CHROMA_PATH}")

    # 4. Test embedding
    print(f"\n4. Testing embedding...")
    try:
        start = time.time()
        emb = get_embedding("test")
        elapsed = time.time() - start
        print(f"   ✅ Embedding works ({len(emb)} dims, {elapsed:.2f}s)")
    except Exception as e:
        print(f"   ❌ Embedding failed: {e}")
        return 1

    print("\n✅ claude-rag initialized successfully!")
    print("\nNext steps:")
    print("  claude-rag index ~/CLAUDE.md     # Index your memory file")
    print("  claude-rag search 'my query'     # Search memories")
    return 0


def cmd_doctor(args):
    """Diagnose claude-rag setup"""
    print("🩺 claude-rag doctor\n")
    issues = []

    # 1. Ollama
    print("Ollama:")
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            print(f"  ✅ Running at {OLLAMA_URL}")
            models = [m["name"] for m in resp.json().get("models", [])]

            # Check embedding model
            if any(EMBED_MODEL in m for m in models):
                print(f"  ✅ Model {EMBED_MODEL} available")
            else:
                print(f"  ❌ Model {EMBED_MODEL} not found")
                issues.append(f"Run: ollama pull {EMBED_MODEL}")
        else:
            print(f"  ❌ Not responding (status {resp.status_code})")
            issues.append("Check Ollama status")
    except requests.exceptions.ConnectionError:
        print(f"  ❌ Not running")
        issues.append("Run: systemctl start ollama")

    # 2. Database
    print("\nDatabase:")
    if os.path.exists(CHROMA_PATH):
        # Get size
        total_size = sum(
            os.path.getsize(os.path.join(dirpath, f))
            for dirpath, _, filenames in os.walk(CHROMA_PATH)
            for f in filenames
        )
        size_str = f"{total_size / 1024 / 1024:.1f} MB" if total_size > 1024*1024 else f"{total_size / 1024:.1f} KB"
        print(f"  ✅ Path exists: {CHROMA_PATH}")
        print(f"  ✅ Size: {size_str}")

        # Check collections
        try:
            client = chromadb.PersistentClient(path=CHROMA_PATH)
            collections = client.list_collections()
            print(f"  ✅ Collections: {len(collections)}")
            for coll in collections:
                print(f"     - {coll.name}: {coll.count()} chunks")
        except Exception as e:
            print(f"  ❌ Error reading DB: {e}")
            issues.append("Database might be corrupted")
    else:
        print(f"  ⚠️  Path doesn't exist: {CHROMA_PATH}")
        issues.append("Run: claude-rag init")

    # 3. MCP Server
    print("\nMCP Server:")
    if MCP_SERVER.exists():
        print(f"  ✅ Script: {MCP_SERVER}")
    else:
        print(f"  ❌ Script not found: {MCP_SERVER}")
        issues.append("MCP server script missing")

    if VENV_PYTHON.exists():
        print(f"  ✅ Venv: {VENV_PYTHON}")
    else:
        print(f"  ❌ Venv not found: {VENV_PYTHON}")
        issues.append("Run: uv venv && uv pip install -r requirements.txt")

    # 4. Claude config
    print("\nClaude Code config:")
    claude_config = Path.home() / ".claude.json"
    if claude_config.exists():
        try:
            config = json.loads(claude_config.read_text())
            # Check if claude-rag is configured in any project
            found = False
            for project, settings in config.get("projects", {}).items():
                if "claude-rag" in settings.get("mcpServers", {}):
                    found = True
                    print(f"  ✅ Configured for: {project}")
            if not found:
                print(f"  ⚠️  Not configured in any project")
                issues.append("Add claude-rag to ~/.claude.json mcpServers")
        except Exception as e:
            print(f"  ❌ Error reading config: {e}")
    else:
        print(f"  ⚠️  Config not found: {claude_config}")

    # Summary
    print("\n" + "="*50)
    if issues:
        print(f"❌ Found {len(issues)} issue(s):\n")
        for issue in issues:
            print(f"  • {issue}")
        return 1
    else:
        print("✅ All checks passed!")
        return 0


def cmd_serve(args):
    """Start the MCP server"""
    if not MCP_SERVER.exists():
        print(f"❌ MCP server not found: {MCP_SERVER}")
        return 1

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

    print(f"🚀 Starting MCP server...")
    print(f"   Python: {python}")
    print(f"   Script: {MCP_SERVER}")
    print(f"   Press Ctrl+C to stop\n")

    try:
        subprocess.run([python, str(MCP_SERVER)], check=True)
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    return 0


def cmd_index(args):
    """Index files into RAG"""
    rag = SimpleRAG()
    path = Path(args.path)
    start = time.time()

    if path.is_dir():
        total = 0
        for f in path.glob("**/*.md"):
            chunks = rag.add_document(str(f))
            print(f"  ✅ {f.name}: {chunks} chunks")
            total += chunks
        print(f"\n📊 Total: {total} chunks in {time.time()-start:.2f}s")
    else:
        chunks = rag.add_document(str(path))
        print(f"✅ {path.name}: {chunks} chunks in {time.time()-start:.2f}s")
    return 0


def cmd_search(args):
    """Search in RAG"""
    rag = SimpleRAG()
    query = " ".join(args.query)
    start = time.time()

    results = rag.search(query, n_results=args.n)
    print(f"🔍 Search completed in {time.time()-start:.2f}s\n")

    for i, r in enumerate(results, 1):
        print(f"[{i}] Score: {r['score']:.3f} | {r['source']}")
        print(f"    {r['text'][:200]}...")
        print()
    return 0


def cmd_stats(args):
    """Show RAG stats"""
    rag = SimpleRAG()
    stats = rag.stats()

    print("📊 RAG Statistics\n")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Database: {stats['path']}")

    # DB size
    if os.path.exists(CHROMA_PATH):
        total_size = sum(
            os.path.getsize(os.path.join(dirpath, f))
            for dirpath, _, filenames in os.walk(CHROMA_PATH)
            for f in filenames
        )
        size_str = f"{total_size / 1024 / 1024:.1f} MB" if total_size > 1024*1024 else f"{total_size / 1024:.1f} KB"
        print(f"Size: {size_str}")
    return 0


def cmd_ui(args):
    """Launch TUI"""
    tui_script = Path(__file__).parent / "rag_tui.py"
    if not tui_script.exists():
        print(f"❌ TUI not found: {tui_script}")
        return 1

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    subprocess.run([python, str(tui_script)])
    return 0


def cmd_web(args):
    """Launch Web UI"""
    web_script = Path(__file__).parent / "web_ui.py"
    if not web_script.exists():
        print(f"❌ Web UI not found: {web_script}")
        return 1

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    port = args.port if hasattr(args, 'port') else 8420

    print(f"🌐 Starting Web UI...")
    print(f"   URL: http://localhost:{port}")
    print(f"   Press Ctrl+C to stop\n")

    subprocess.run([python, str(web_script), "--port", str(port)])
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="claude-rag",
        description="Semantic memory for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  claude-rag init                    # Setup claude-rag
  claude-rag doctor                  # Diagnose issues
  claude-rag index ~/CLAUDE.md       # Index a file
  claude-rag search "my query"       # Search memories
  claude-rag serve                   # Start MCP server
  claude-rag ui                      # Launch TUI
  claude-rag web                     # Launch Web UI
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init
    subparsers.add_parser("init", help="Initialize claude-rag")

    # doctor
    subparsers.add_parser("doctor", help="Diagnose setup issues")

    # serve
    subparsers.add_parser("serve", help="Start MCP server")

    # index
    p_index = subparsers.add_parser("index", help="Index files")
    p_index.add_argument("path", help="File or directory to index")

    # search
    p_search = subparsers.add_parser("search", help="Search memories")
    p_search.add_argument("query", nargs="+", help="Search query")
    p_search.add_argument("-n", type=int, default=3, help="Number of results")

    # stats
    subparsers.add_parser("stats", help="Show statistics")

    # ui
    subparsers.add_parser("ui", help="Launch TUI")

    # web
    p_web = subparsers.add_parser("web", help="Launch Web UI")
    p_web.add_argument("-p", "--port", type=int, default=8420, help="Port (default: 8420)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "init": cmd_init,
        "doctor": cmd_doctor,
        "serve": cmd_serve,
        "index": cmd_index,
        "search": cmd_search,
        "stats": cmd_stats,
        "ui": cmd_ui,
        "web": cmd_web,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
