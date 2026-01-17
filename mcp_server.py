#!/usr/bin/env python3
"""
Claude Code RAG - MCP Server
Provides semantic search tools for Claude Code
"""
import os
import re
import hashlib
import time
import json
from pathlib import Path
from datetime import datetime

import chromadb
import requests
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configuration
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
CHROMA_PATH = os.environ.get("CHROMA_PATH", os.path.expanduser("~/.local/share/claude-memory"))

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    ".md": "markdown",
    ".txt": "text",
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sh": "shell",
    ".toml": "toml",
    ".fish": "shell",
}

# Initialize server
server = Server("claude-rag")

# ChromaDB client (lazy init)
_client = None
_collection = None


def get_collection():
    """Get or create ChromaDB collection"""
    global _client, _collection
    if _collection is None:
        os.makedirs(CHROMA_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _client.get_or_create_collection(
            name="claude_memory",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


def get_embedding(text: str) -> list:
    """Get embedding from Ollama"""
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=30
    )
    return resp.json()["embedding"]


def chunk_markdown(content: str, chunk_size: int = 500) -> list[dict]:
    """Split markdown by headers, fallback to size-based chunking"""
    chunks = []

    # Split by ## headers
    sections = re.split(r'\n(?=## )', content)

    for section in sections:
        if len(section) <= chunk_size:
            if section.strip():
                chunks.append({"text": section.strip(), "type": "section"})
        else:
            # Split large sections by size with overlap
            for i in range(0, len(section), chunk_size - 50):
                chunk = section[i:i + chunk_size]
                if chunk.strip():
                    chunks.append({"text": chunk.strip(), "type": "chunk"})

    return chunks if chunks else [{"text": content[:chunk_size], "type": "chunk"}]


def chunk_python(content: str, chunk_size: int = 500) -> list[dict]:
    """Split Python code by functions and classes"""
    chunks = []

    # Match functions and classes
    pattern = r'^((?:async\s+)?def\s+\w+|class\s+\w+)'
    lines = content.split('\n')
    current_chunk = []
    current_type = "module"

    for line in lines:
        match = re.match(pattern, line)
        if match:
            # Save previous chunk
            if current_chunk:
                text = '\n'.join(current_chunk).strip()
                if text:
                    chunks.append({"text": text, "type": current_type})
            current_chunk = [line]
            current_type = "function" if "def " in match.group(1) else "class"
        else:
            current_chunk.append(line)

    # Don't forget the last chunk
    if current_chunk:
        text = '\n'.join(current_chunk).strip()
        if text:
            chunks.append({"text": text, "type": current_type})

    # Fallback if no functions/classes found
    if not chunks:
        return [{"text": content[i:i+chunk_size], "type": "chunk"}
                for i in range(0, len(content), chunk_size - 50) if content[i:i+chunk_size].strip()]

    return chunks


def chunk_javascript(content: str, chunk_size: int = 500) -> list[dict]:
    """Split JavaScript/TypeScript by functions"""
    chunks = []

    # Match functions, const/let arrows, exports
    pattern = r'^((?:export\s+)?(?:async\s+)?(?:function\s+\w+|const\s+\w+\s*=|let\s+\w+\s*=|class\s+\w+))'
    lines = content.split('\n')
    current_chunk = []
    current_type = "module"

    for line in lines:
        match = re.match(pattern, line)
        if match:
            if current_chunk:
                text = '\n'.join(current_chunk).strip()
                if text:
                    chunks.append({"text": text, "type": current_type})
            current_chunk = [line]
            current_type = "function"
        else:
            current_chunk.append(line)

    if current_chunk:
        text = '\n'.join(current_chunk).strip()
        if text:
            chunks.append({"text": text, "type": current_type})

    if not chunks:
        return [{"text": content[i:i+chunk_size], "type": "chunk"}
                for i in range(0, len(content), chunk_size - 50) if content[i:i+chunk_size].strip()]

    return chunks


def chunk_generic(content: str, chunk_size: int = 500) -> list[dict]:
    """Generic size-based chunking with overlap"""
    chunks = []
    overlap = 50

    for i in range(0, len(content), chunk_size - overlap):
        chunk = content[i:i + chunk_size]
        if chunk.strip():
            chunks.append({"text": chunk.strip(), "type": "chunk"})

    return chunks if chunks else [{"text": content, "type": "chunk"}]


def chunk_content(content: str, file_type: str, chunk_size: int = 500) -> list[dict]:
    """Route to appropriate chunker based on file type"""
    if file_type == "markdown":
        return chunk_markdown(content, chunk_size)
    elif file_type == "python":
        return chunk_python(content, chunk_size)
    elif file_type in ("javascript", "typescript"):
        return chunk_javascript(content, chunk_size)
    else:
        return chunk_generic(content, chunk_size)


def check_ollama_health() -> dict:
    """Check if Ollama is running and model is available"""
    try:
        # Check if Ollama is running
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code != 200:
            return {"ok": False, "error": "Ollama not responding"}

        # Check if embedding model is available
        models = [m["name"] for m in resp.json().get("models", [])]
        model_available = any(EMBED_MODEL in m for m in models)

        if not model_available:
            return {
                "ok": False,
                "error": f"Model '{EMBED_MODEL}' not found. Run: ollama pull {EMBED_MODEL}"
            }

        return {"ok": True, "ollama": "running", "model": EMBED_MODEL}

    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "Ollama not running. Start with: systemctl start ollama"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@server.list_tools()
async def list_tools():
    """List available RAG tools"""
    return [
        Tool(
            name="rag_search",
            description="Search the RAG memory for relevant information. Use this to find context about the system, previous configurations, or any indexed documentation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query - what you're looking for"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return (default: 3)",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="rag_index",
            description="Index a file or directory into the RAG memory. Use this after modifying CLAUDE.md or adding new documentation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to file or directory to index (supports ~ expansion)"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="rag_store",
            description="Manually store a piece of information in the RAG memory. Use this to save important decisions, bug fixes, or any context you want to remember.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The content to store"
                    },
                    "memory_type": {
                        "type": "string",
                        "description": "Type of memory: context, decision, bugfix, architecture, preference, snippet",
                        "enum": ["context", "decision", "bugfix", "architecture", "preference", "snippet"],
                        "default": "context"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for categorization"
                    }
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="rag_stats",
            description="Get RAG memory statistics - total chunks indexed and database path.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="rag_health",
            description="Check if the RAG system is healthy - Ollama running, model available, database accessible.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls"""

    if name == "rag_search":
        query = arguments.get("query", "")
        n_results = arguments.get("n_results", 3)

        if not query:
            return [TextContent(type="text", text="Error: query is required")]

        try:
            start = time.time()
            collection = get_collection()
            query_embedding = get_embedding(query)

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )

            if not results["documents"][0]:
                return [TextContent(type="text", text="No results found.")]

            output = f"Search completed in {time.time()-start:.2f}s\n\n"
            for i, (doc, meta, dist) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ), 1):
                score = 1 - dist
                source = meta.get("source", "unknown")
                mem_type = meta.get("memory_type", "")
                type_str = f" [{mem_type}]" if mem_type else ""
                output += f"[{i}] Score: {score:.3f}{type_str} | Source: {source}\n"
                output += f"    {doc[:300]}...\n\n"

            return [TextContent(type="text", text=output)]

        except requests.exceptions.ConnectionError:
            return [TextContent(type="text", text="Error: Ollama not running. Start with: systemctl start ollama")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_index":
        path_str = arguments.get("path", "")
        if not path_str:
            return [TextContent(type="text", text="Error: path is required")]

        try:
            path = Path(os.path.expanduser(path_str))
            if not path.exists():
                return [TextContent(type="text", text=f"Error: Path not found: {path}")]

            start = time.time()
            collection = get_collection()
            total_chunks = 0
            indexed_files = []

            # Find all supported files
            if path.is_dir():
                files = []
                for ext in SUPPORTED_EXTENSIONS:
                    files.extend(path.glob(f"**/*{ext}"))
            else:
                files = [path]

            for filepath in files:
                ext = filepath.suffix.lower()
                file_type = SUPPORTED_EXTENSIONS.get(ext, "text")

                try:
                    content = filepath.read_text()
                except UnicodeDecodeError:
                    continue  # Skip binary files

                doc_id = hashlib.md5(str(filepath).encode()).hexdigest()[:8]
                file_hash = hashlib.md5(content.encode()).hexdigest()[:8]

                # Smart chunking based on file type
                chunks = chunk_content(content, file_type)

                ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
                embeddings = [get_embedding(c["text"]) for c in chunks]
                metadatas = [{
                    "source": str(filepath),
                    "file_type": file_type,
                    "file_hash": file_hash,
                    "chunk_index": i,
                    "chunk_type": c["type"],
                    "indexed_at": datetime.now().isoformat()
                } for i, c in enumerate(chunks)]

                collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=[c["text"] for c in chunks],
                    metadatas=metadatas
                )
                total_chunks += len(chunks)
                indexed_files.append(f"{filepath.name} ({len(chunks)} chunks)")

            elapsed = time.time() - start
            files_list = "\n".join(f"  - {f}" for f in indexed_files[:10])
            if len(indexed_files) > 10:
                files_list += f"\n  ... and {len(indexed_files) - 10} more"

            return [TextContent(
                type="text",
                text=f"Indexed {len(indexed_files)} file(s): {total_chunks} chunks in {elapsed:.2f}s\n\n{files_list}"
            )]

        except requests.exceptions.ConnectionError:
            return [TextContent(type="text", text="Error: Ollama not running. Start with: systemctl start ollama")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_store":
        content = arguments.get("content", "")
        memory_type = arguments.get("memory_type", "context")
        tags = arguments.get("tags", [])

        if not content:
            return [TextContent(type="text", text="Error: content is required")]

        try:
            collection = get_collection()

            # Generate unique ID
            doc_id = hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:12]

            embedding = get_embedding(content)
            metadata = {
                "source": "manual",
                "memory_type": memory_type,
                "tags": ",".join(tags) if tags else "",
                "indexed_at": datetime.now().isoformat()
            }

            collection.upsert(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[metadata]
            )

            return [TextContent(
                type="text",
                text=f"Stored memory [{memory_type}] with ID: {doc_id}"
            )]

        except requests.exceptions.ConnectionError:
            return [TextContent(type="text", text="Error: Ollama not running. Start with: systemctl start ollama")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_stats":
        try:
            collection = get_collection()
            count = collection.count()

            # Get some metadata stats
            all_meta = collection.get(include=["metadatas"])
            types = {}
            sources = set()

            for meta in all_meta.get("metadatas", []):
                mem_type = meta.get("memory_type", meta.get("file_type", "unknown"))
                types[mem_type] = types.get(mem_type, 0) + 1
                sources.add(meta.get("source", "unknown"))

            types_str = "\n".join(f"  - {t}: {c}" for t, c in sorted(types.items()))

            return [TextContent(
                type="text",
                text=f"RAG Statistics:\n- Total chunks: {count}\n- Unique sources: {len(sources)}\n- Types:\n{types_str}\n- Database: {CHROMA_PATH}"
            )]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_health":
        try:
            health = check_ollama_health()

            if not health["ok"]:
                return [TextContent(type="text", text=f"❌ RAG Health Check FAILED\n\nError: {health['error']}")]

            # Check ChromaDB
            collection = get_collection()
            count = collection.count()

            return [TextContent(
                type="text",
                text=f"✅ RAG Health Check OK\n\n- Ollama: running\n- Model: {EMBED_MODEL}\n- Database: {CHROMA_PATH}\n- Chunks indexed: {count}"
            )]

        except Exception as e:
            return [TextContent(type="text", text=f"❌ RAG Health Check FAILED\n\nError: {str(e)}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
