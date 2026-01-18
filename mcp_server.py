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

# Import session parser for auto-capture
from session_parser import parse_recent_sessions, get_all_sessions

# Configuration
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
CHROMA_PATH = os.environ.get("CHROMA_PATH", os.path.expanduser("~/.local/share/claude-memory"))
PROJECT_PATH = os.environ.get("PROJECT_PATH", os.getcwd())

# Scopes
SCOPE_GLOBAL = "global"
SCOPE_PROJECT = "project"
SCOPE_ALL = "all"

# Sync state file (tracks file hashes for change detection)
SYNC_STATE_FILE = os.path.join(CHROMA_PATH, "sync_state.json")

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

# ChromaDB clients (lazy init)
_clients = {}  # scope -> client
_collections = {}  # scope -> collection


def get_project_id() -> str:
    """Generate a unique project ID from the project path"""
    return hashlib.md5(PROJECT_PATH.encode()).hexdigest()[:12]


def get_db_path(scope: str) -> str:
    """Get database path for a scope"""
    if scope == SCOPE_GLOBAL:
        return os.path.join(CHROMA_PATH, "global")
    else:
        project_id = get_project_id()
        return os.path.join(CHROMA_PATH, "projects", project_id)


def get_collection(scope: str = SCOPE_PROJECT):
    """Get or create ChromaDB collection for a scope"""
    global _clients, _collections

    if scope not in _collections:
        db_path = get_db_path(scope)
        os.makedirs(db_path, exist_ok=True)
        _clients[scope] = chromadb.PersistentClient(path=db_path)
        _collections[scope] = _clients[scope].get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"}
        )
    return _collections[scope]


def get_collections_for_scope(scope: str) -> list:
    """Get list of (collection, scope_name) tuples based on scope"""
    if scope == SCOPE_ALL:
        return [(get_collection(SCOPE_PROJECT), SCOPE_PROJECT), (get_collection(SCOPE_GLOBAL), SCOPE_GLOBAL)]
    elif scope == SCOPE_GLOBAL:
        return [(get_collection(SCOPE_GLOBAL), SCOPE_GLOBAL)]
    else:
        return [(get_collection(SCOPE_PROJECT), SCOPE_PROJECT)]


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


# ============================================================================
# Sync State Management (for bidirectional sync)
# ============================================================================

def get_sync_state() -> dict:
    """Load sync state from disk"""
    if os.path.exists(SYNC_STATE_FILE):
        try:
            with open(SYNC_STATE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_sync_state(state: dict):
    """Save sync state to disk"""
    os.makedirs(os.path.dirname(SYNC_STATE_FILE), exist_ok=True)
    with open(SYNC_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def get_file_hash(filepath: str) -> str:
    """Get SHA256 hash of file content"""
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def generate_chunk_id(content: str, source: str, chunk_index: int) -> str:
    """Generate unique ID based on content hash (enables auto-dedup via upsert)"""
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    source_hash = hashlib.md5(source.encode()).hexdigest()[:8]
    return f"{source_hash}_{chunk_index}_{content_hash}"


def get_indexed_sources(scope: str) -> set:
    """Get all source files currently indexed in a scope"""
    try:
        coll = get_collection(scope)
        data = coll.get(include=["metadatas"])
        sources = set()
        for meta in data.get("metadatas", []):
            source = meta.get("source", "")
            if source.startswith("file:"):
                sources.add(source.replace("file:", ""))
        return sources
    except Exception:
        return set()


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
                    },
                    "memory_type": {
                        "type": "string",
                        "description": "Filter by memory type: context, decision, bugfix, architecture, preference, snippet",
                        "enum": ["context", "decision", "bugfix", "architecture", "preference", "snippet"]
                    },
                    "scope": {
                        "type": "string",
                        "description": "Memory scope: 'project' (current project), 'global' (system-wide), 'all' (both, default)",
                        "enum": ["project", "global", "all"],
                        "default": "all"
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
                    },
                    "scope": {
                        "type": "string",
                        "description": "Memory scope: 'project' (default) or 'global' (system-wide knowledge)",
                        "enum": ["project", "global"],
                        "default": "project"
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
                    },
                    "scope": {
                        "type": "string",
                        "description": "Memory scope: 'project' (default) or 'global' (system-wide knowledge)",
                        "enum": ["project", "global"],
                        "default": "project"
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
                "properties": {
                    "scope": {
                        "type": "string",
                        "description": "Memory scope: 'project', 'global', or 'all' (default)",
                        "enum": ["project", "global", "all"],
                        "default": "all"
                    }
                }
            }
        ),
        Tool(
            name="rag_health",
            description="Check if the RAG system is healthy - Ollama running, model available, database accessible.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="rag_forget",
            description="Delete memories from the RAG database. Search for memories matching a query and delete them.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find memories to delete"
                    },
                    "memory_id": {
                        "type": "string",
                        "description": "Specific memory ID to delete (alternative to query)"
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be true to actually delete. If false, just shows what would be deleted.",
                        "default": False
                    },
                    "scope": {
                        "type": "string",
                        "description": "Memory scope: 'project' (default) or 'global'",
                        "enum": ["project", "global"],
                        "default": "project"
                    }
                }
            }
        ),
        Tool(
            name="rag_list",
            description="List memories in the RAG database with optional filtering.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_type": {
                        "type": "string",
                        "description": "Filter by memory type: context, decision, bugfix, architecture, preference, snippet",
                        "enum": ["context", "decision", "bugfix", "architecture", "preference", "snippet"]
                    },
                    "source": {
                        "type": "string",
                        "description": "Filter by source (partial match)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 20)",
                        "default": 20
                    },
                    "scope": {
                        "type": "string",
                        "description": "Memory scope: 'project', 'global', or 'all' (default)",
                        "enum": ["project", "global", "all"],
                        "default": "all"
                    }
                }
            }
        ),
        Tool(
            name="rag_export",
            description="Export memories to a context file (AGENTS.md, CLAUDE.md, GEMINI.md, etc.) for use with AI coding agents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "description": "Output format: 'agents' (AGENTS.md - universal), 'claude' (CLAUDE.md), 'gemini' (GEMINI.md), 'aider' (CONVENTIONS.md), 'cursor' (.cursor/rules/)",
                        "enum": ["agents", "claude", "gemini", "aider", "cursor"],
                        "default": "agents"
                    },
                    "scope": {
                        "type": "string",
                        "description": "Memory scope to export: 'project', 'global', or 'all'",
                        "enum": ["project", "global", "all"],
                        "default": "all"
                    },
                    "memory_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by memory types (default: all types). Options: decision, architecture, preference, bugfix, snippet, context"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Custom output path (default: auto based on format)"
                    },
                    "create_symlinks": {
                        "type": "boolean",
                        "description": "Create symlinks for other agents (e.g., CLAUDE.md -> AGENTS.md)",
                        "default": False
                    },
                    "max_entries": {
                        "type": "integer",
                        "description": "Maximum entries per section (default: 50)",
                        "default": 50
                    }
                }
            }
        ),
        Tool(
            name="rag_capture",
            description="Auto-capture memories from recent Claude Code sessions. Parses session files and extracts decisions, bugfixes, architecture choices, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_sessions": {
                        "type": "integer",
                        "description": "Maximum number of recent sessions to parse (default: 3)",
                        "default": 3
                    },
                    "min_confidence": {
                        "type": "number",
                        "description": "Minimum confidence threshold for extraction (0-1, default: 0.7)",
                        "default": 0.7
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, show what would be captured without storing (default: false)",
                        "default": False
                    },
                    "scope": {
                        "type": "string",
                        "description": "Memory scope: 'project' (default) or 'global'",
                        "enum": ["project", "global"],
                        "default": "project"
                    }
                }
            }
        ),
        Tool(
            name="rag_sync",
            description="Sync watched files with RAG memory. Detects changes via content hash and reindexes only modified files. Use this to keep RAG in sync with your CLAUDE.md and other context files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Paths to sync (default: ~/CLAUDE.md + project CLAUDE.md). Supports ~ expansion."
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force reindex even if content unchanged",
                        "default": False
                    },
                    "scope": {
                        "type": "string",
                        "description": "Memory scope: 'project' (default) or 'global'",
                        "enum": ["project", "global"],
                        "default": "project"
                    }
                }
            }
        ),
        Tool(
            name="rag_backup",
            description="Export RAG memory to a JSON backup file. Use this to save your memories before major changes or for migration.",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Output file path (default: ~/claude-rag-backup-{timestamp}.json)"
                    },
                    "scope": {
                        "type": "string",
                        "description": "Memory scope to backup: 'project', 'global', or 'all' (default)",
                        "enum": ["project", "global", "all"],
                        "default": "all"
                    }
                }
            }
        ),
        Tool(
            name="rag_restore",
            description="Restore RAG memory from a JSON backup file. Use this to recover memories or migrate to a new system.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {
                        "type": "string",
                        "description": "Path to the backup JSON file"
                    },
                    "mode": {
                        "type": "string",
                        "description": "Restore mode: 'merge' (add to existing, default) or 'replace' (clear and restore)",
                        "enum": ["merge", "replace"],
                        "default": "merge"
                    },
                    "scope": {
                        "type": "string",
                        "description": "Target scope for restore: 'project' or 'global' (default: use scope from backup)",
                        "enum": ["project", "global"]
                    }
                },
                "required": ["input_path"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls"""

    if name == "rag_search":
        query = arguments.get("query", "")
        n_results = arguments.get("n_results", 3)
        memory_type = arguments.get("memory_type")
        scope = arguments.get("scope", SCOPE_ALL)

        if not query:
            return [TextContent(type="text", text="Error: query is required")]

        try:
            start = time.time()
            query_embedding = get_embedding(query)

            # Build where filter if memory_type specified
            where_filter = None
            if memory_type:
                where_filter = {"memory_type": memory_type}

            # Collect results from all relevant collections
            all_results = []
            collections = get_collections_for_scope(scope)

            for coll, coll_scope in collections:
                try:
                    results = coll.query(
                        query_embeddings=[query_embedding],
                        n_results=n_results * 2,
                        where=where_filter
                    )
                    if results["documents"][0]:
                        for doc, meta, dist in zip(
                            results["documents"][0],
                            results["metadatas"][0],
                            results["distances"][0]
                        ):
                            meta["_scope"] = coll_scope
                            all_results.append((doc, meta, dist))
                except Exception:
                    continue

            if not all_results:
                filter_msg = f" (type: {memory_type})" if memory_type else ""
                return [TextContent(type="text", text=f"No results found{filter_msg}.")]

            # Sort by distance (lower is better)
            all_results.sort(key=lambda x: x[2])

            output = f"Search completed in {time.time()-start:.2f}s (scope: {scope})"
            if memory_type:
                output += f" (type: {memory_type})"
            output += "\n\n"

            for i, (doc, meta, dist) in enumerate(all_results[:n_results]):
                score = 1 - dist
                source = meta.get("source", "unknown")
                mem_type = meta.get("memory_type", "")
                mem_scope = meta.get("_scope", "")
                type_str = f" [{mem_type}]" if mem_type else ""
                scope_str = f" 🌐" if mem_scope == "global" else " 📁"
                output += f"[{i+1}]{scope_str} Score: {score:.3f}{type_str} | Source: {source}\n"
                output += f"    {doc[:300]}...\n\n"

            return [TextContent(type="text", text=output)]

        except requests.exceptions.ConnectionError:
            return [TextContent(type="text", text="Error: Ollama not running. Start with: systemctl start ollama")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_index":
        path_str = arguments.get("path", "")
        scope = arguments.get("scope", SCOPE_PROJECT)

        if not path_str:
            return [TextContent(type="text", text="Error: path is required")]

        try:
            path = Path(os.path.expanduser(path_str))
            if not path.exists():
                return [TextContent(type="text", text=f"Error: Path not found: {path}")]

            start = time.time()
            collection = get_collection(scope)
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

            scope_icon = "🌐" if scope == SCOPE_GLOBAL else "📁"
            return [TextContent(
                type="text",
                text=f"{scope_icon} Indexed {len(indexed_files)} file(s) to {scope}: {total_chunks} chunks in {elapsed:.2f}s\n\n{files_list}"
            )]

        except requests.exceptions.ConnectionError:
            return [TextContent(type="text", text="Error: Ollama not running. Start with: systemctl start ollama")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_store":
        content = arguments.get("content", "")
        memory_type = arguments.get("memory_type", "context")
        tags = arguments.get("tags", [])
        scope = arguments.get("scope", SCOPE_PROJECT)

        if not content:
            return [TextContent(type="text", text="Error: content is required")]

        try:
            collection = get_collection(scope)

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

            scope_icon = "🌐" if scope == SCOPE_GLOBAL else "📁"
            return [TextContent(
                type="text",
                text=f"{scope_icon} Stored memory [{memory_type}] to {scope} with ID: {doc_id}"
            )]

        except requests.exceptions.ConnectionError:
            return [TextContent(type="text", text="Error: Ollama not running. Start with: systemctl start ollama")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_stats":
        scope = arguments.get("scope", SCOPE_ALL)
        try:
            output = "📊 RAG Statistics\n\n"
            total_count = 0
            all_types = {}
            all_sources = set()

            scopes_to_check = [SCOPE_PROJECT, SCOPE_GLOBAL] if scope == SCOPE_ALL else [scope]

            for s in scopes_to_check:
                try:
                    coll = get_collection(s)
                    count = coll.count()
                    total_count += count

                    scope_icon = "🌐" if s == SCOPE_GLOBAL else "📁"
                    output += f"{scope_icon} **{s.capitalize()}**: {count} chunks\n"

                    if count > 0:
                        all_meta = coll.get(include=["metadatas"])
                        for meta in all_meta.get("metadatas", []):
                            mem_type = meta.get("memory_type", meta.get("file_type", "unknown"))
                            all_types[mem_type] = all_types.get(mem_type, 0) + 1
                            all_sources.add(meta.get("source", "unknown"))
                except Exception:
                    output += f"  {s}: (not initialized)\n"

            output += f"\n**Total**: {total_count} chunks\n"
            output += f"**Unique sources**: {len(all_sources)}\n"
            if all_types:
                output += "**Types**:\n"
                for t, c in sorted(all_types.items()):
                    output += f"  - {t}: {c}\n"
            output += f"\n**Project**: {PROJECT_PATH}\n"
            output += f"**Database**: {CHROMA_PATH}"

            return [TextContent(type="text", text=output)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_health":
        try:
            health = check_ollama_health()

            if not health["ok"]:
                return [TextContent(type="text", text=f"❌ RAG Health Check FAILED\n\nError: {health['error']}")]

            # Check ChromaDB for both scopes
            project_count = get_collection(SCOPE_PROJECT).count()
            global_count = get_collection(SCOPE_GLOBAL).count()

            return [TextContent(
                type="text",
                text=f"✅ RAG Health Check OK\n\n- Ollama: running\n- Model: {EMBED_MODEL}\n- Project: {PROJECT_PATH}\n- 📁 Project memories: {project_count}\n- 🌐 Global memories: {global_count}\n- Database: {CHROMA_PATH}"
            )]

        except Exception as e:
            return [TextContent(type="text", text=f"❌ RAG Health Check FAILED\n\nError: {str(e)}")]

    elif name == "rag_forget":
        query = arguments.get("query", "")
        memory_id = arguments.get("memory_id", "")
        confirm = arguments.get("confirm", False)
        scope = arguments.get("scope", SCOPE_PROJECT)

        if not query and not memory_id:
            return [TextContent(type="text", text="Error: either 'query' or 'memory_id' is required")]

        try:
            collection = get_collection(scope)

            if memory_id:
                # Delete by specific ID
                try:
                    collection.delete(ids=[memory_id])
                    scope_icon = "🌐" if scope == SCOPE_GLOBAL else "📁"
                    return [TextContent(type="text", text=f"{scope_icon} Deleted memory with ID: {memory_id}")]
                except Exception:
                    return [TextContent(type="text", text=f"Memory ID not found: {memory_id}")]

            # Search for memories matching query
            query_embedding = get_embedding(query)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=10
            )

            if not results["documents"][0]:
                return [TextContent(type="text", text="No memories found matching query.")]

            ids_to_delete = results["ids"][0]
            docs = results["documents"][0]
            metas = results["metadatas"][0]

            if not confirm:
                # Preview mode
                output = f"⚠️ Found {len(ids_to_delete)} memories to delete:\n\n"
                for i, (doc_id, doc, meta) in enumerate(zip(ids_to_delete, docs, metas), 1):
                    source = meta.get("source", "unknown")
                    output += f"[{i}] ID: {doc_id} | Source: {source}\n"
                    output += f"    {doc[:100]}...\n\n"
                output += "Set confirm=true to delete these memories."
                return [TextContent(type="text", text=output)]

            # Actually delete
            collection.delete(ids=ids_to_delete)
            return [TextContent(type="text", text=f"✅ Deleted {len(ids_to_delete)} memories.")]

        except requests.exceptions.ConnectionError:
            return [TextContent(type="text", text="Error: Ollama not running. Start with: systemctl start ollama")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_list":
        memory_type = arguments.get("memory_type")
        source_filter = arguments.get("source", "")
        limit = arguments.get("limit", 20)
        scope = arguments.get("scope", SCOPE_ALL)

        try:
            filtered = []
            scopes_to_check = [SCOPE_PROJECT, SCOPE_GLOBAL] if scope == SCOPE_ALL else [scope]

            for s in scopes_to_check:
                try:
                    coll = get_collection(s)
                    all_data = coll.get(include=["documents", "metadatas"])

                    if not all_data["documents"]:
                        continue

                    for doc_id, doc, meta in zip(all_data["ids"], all_data["documents"], all_data["metadatas"]):
                        if memory_type and meta.get("memory_type") != memory_type:
                            continue
                        if source_filter and source_filter.lower() not in meta.get("source", "").lower():
                            continue
                        meta["_scope"] = s
                        filtered.append((doc_id, doc, meta))
                except Exception:
                    continue

            if not filtered:
                filter_msg = []
                if memory_type:
                    filter_msg.append(f"type={memory_type}")
                if source_filter:
                    filter_msg.append(f"source contains '{source_filter}'")
                return [TextContent(type="text", text=f"No memories found with filters: {', '.join(filter_msg)}")]

            # Sort by indexed_at if available
            filtered.sort(key=lambda x: x[2].get("indexed_at", ""), reverse=True)
            filtered = filtered[:limit]

            output = f"Listing {len(filtered)} memories (scope: {scope})"
            if memory_type:
                output += f" (type: {memory_type})"
            if source_filter:
                output += f" (source: *{source_filter}*)"
            output += ":\n\n"

            for doc_id, doc, meta in filtered:
                source = meta.get("source", "unknown")
                mem_type = meta.get("memory_type", meta.get("file_type", ""))
                mem_scope = meta.get("_scope", "")
                indexed_at = meta.get("indexed_at", "")[:10]
                type_str = f"[{mem_type}] " if mem_type else ""
                scope_icon = "🌐" if mem_scope == "global" else "📁"
                output += f"• {scope_icon} {type_str}{doc_id} | {source}"
                if indexed_at:
                    output += f" | {indexed_at}"
                output += f"\n  {doc[:80]}...\n\n"

            return [TextContent(type="text", text=output)]

        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_capture":
        max_sessions = arguments.get("max_sessions", 3)
        min_confidence = arguments.get("min_confidence", 0.7)
        dry_run = arguments.get("dry_run", False)
        scope = arguments.get("scope", SCOPE_PROJECT)

        try:
            collection = get_collection(scope)
            captured = []
            skipped = 0

            for memory in parse_recent_sessions(max_sessions=max_sessions):
                if memory.confidence < min_confidence:
                    skipped += 1
                    continue

                if dry_run:
                    captured.append({
                        "type": memory.memory_type,
                        "confidence": memory.confidence,
                        "content": memory.content[:100] + "...",
                        "tags": memory.tags
                    })
                else:
                    # Store in RAG
                    doc_id = hashlib.md5(f"{memory.content}{memory.timestamp}".encode()).hexdigest()[:12]
                    embedding = get_embedding(memory.content)
                    metadata = {
                        "source": f"session:{memory.source}",
                        "memory_type": memory.memory_type,
                        "tags": ",".join(memory.tags) if memory.tags else "",
                        "confidence": str(memory.confidence),
                        "indexed_at": datetime.now().isoformat(),
                        "auto_captured": "true"
                    }

                    collection.upsert(
                        ids=[doc_id],
                        embeddings=[embedding],
                        documents=[memory.content],
                        metadatas=[metadata]
                    )
                    captured.append({
                        "type": memory.memory_type,
                        "id": doc_id
                    })

            if dry_run:
                output = f"🔍 DRY RUN - Would capture {len(captured)} memories (skipped {skipped} below confidence {min_confidence}):\n\n"
                by_type = {}
                for mem in captured:
                    t = mem["type"]
                    by_type[t] = by_type.get(t, 0) + 1
                for t, count in sorted(by_type.items()):
                    output += f"  • {t}: {count}\n"
                output += f"\nSample memories:\n"
                for mem in captured[:5]:
                    output += f"\n[{mem['type']}] {mem['content']}\n"
                    if mem['tags']:
                        output += f"  Tags: {', '.join(mem['tags'])}\n"
            else:
                output = f"✅ Captured {len(captured)} memories from {max_sessions} session(s) (skipped {skipped}):\n\n"
                by_type = {}
                for mem in captured:
                    t = mem["type"]
                    by_type[t] = by_type.get(t, 0) + 1
                for t, count in sorted(by_type.items()):
                    output += f"  • {t}: {count}\n"

            return [TextContent(type="text", text=output)]

        except requests.exceptions.ConnectionError:
            return [TextContent(type="text", text="Error: Ollama not running. Start with: systemctl start ollama")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_sync":
        paths = arguments.get("paths", [])
        force = arguments.get("force", False)
        scope = arguments.get("scope", SCOPE_PROJECT)

        # Default paths if not specified
        if not paths:
            paths = [
                os.path.expanduser("~/CLAUDE.md"),
                os.path.join(PROJECT_PATH, "CLAUDE.md"),
            ]
        else:
            paths = [os.path.expanduser(p) for p in paths]

        try:
            collection = get_collection(scope)
            sync_state = get_sync_state()
            updated = []
            skipped = []
            not_found = []

            for filepath in paths:
                if not os.path.exists(filepath):
                    not_found.append(filepath)
                    continue

                # Get current file hash
                current_hash = get_file_hash(filepath)
                state_key = f"{scope}:{filepath}"
                stored_hash = sync_state.get(state_key, {}).get("hash")

                # Skip if unchanged (unless force)
                if not force and current_hash == stored_hash:
                    skipped.append(filepath)
                    continue

                # Delete old chunks for this file (clean reindex)
                source_pattern = f"file:{filepath}"
                try:
                    existing = collection.get(
                        where={"source": source_pattern},
                        include=["metadatas"]
                    )
                    if existing["ids"]:
                        collection.delete(ids=existing["ids"])
                except Exception:
                    pass  # Collection might not have where filter support

                # Read and chunk the file
                content = Path(filepath).read_text()
                ext = Path(filepath).suffix.lower()
                file_type = SUPPORTED_EXTENSIONS.get(ext, "text")
                chunks = chunk_content(content, file_type)

                # Index chunks with hash-based IDs (auto-dedup)
                chunk_count = 0
                for i, chunk in enumerate(chunks):
                    chunk_id = generate_chunk_id(chunk["text"], filepath, i)
                    embedding = get_embedding(chunk["text"])
                    metadata = {
                        "source": source_pattern,
                        "file_type": file_type,
                        "memory_type": "context",
                        "chunk_index": str(i),
                        "file_hash": current_hash[:16],
                        "indexed_at": datetime.now().isoformat()
                    }

                    collection.upsert(
                        ids=[chunk_id],
                        embeddings=[embedding],
                        documents=[chunk["text"]],
                        metadatas=[metadata]
                    )
                    chunk_count += 1

                # Update sync state
                sync_state[state_key] = {
                    "hash": current_hash,
                    "indexed_at": datetime.now().isoformat(),
                    "chunks": chunk_count
                }
                updated.append({"path": filepath, "chunks": chunk_count})

            # Save sync state
            save_sync_state(sync_state)

            # Build output
            output = f"🔄 Sync completed (scope: {scope})\n\n"

            if updated:
                output += f"**Updated ({len(updated)}):**\n"
                for item in updated:
                    output += f"  ✅ {item['path']} ({item['chunks']} chunks)\n"
                output += "\n"

            if skipped:
                output += f"**Unchanged ({len(skipped)}):**\n"
                for path in skipped:
                    output += f"  ⏭️  {path}\n"
                output += "\n"

            if not_found:
                output += f"**Not found ({len(not_found)}):**\n"
                for path in not_found:
                    output += f"  ❌ {path}\n"

            if not updated and not skipped and not not_found:
                output += "No files to sync.\n"

            return [TextContent(type="text", text=output)]

        except requests.exceptions.ConnectionError:
            return [TextContent(type="text", text="Error: Ollama not running. Start with: systemctl start ollama")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_backup":
        output_path = arguments.get("output_path", "")
        scope = arguments.get("scope", SCOPE_ALL)

        try:
            # Default output path with timestamp
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.expanduser(f"~/claude-rag-backup-{timestamp}.json")
            else:
                output_path = os.path.expanduser(output_path)

            backup_data = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "scope": scope,
                "project_path": PROJECT_PATH,
                "collections": {}
            }

            scopes_to_backup = [SCOPE_PROJECT, SCOPE_GLOBAL] if scope == SCOPE_ALL else [scope]
            total_memories = 0

            for s in scopes_to_backup:
                try:
                    coll = get_collection(s)
                    data = coll.get(include=["documents", "metadatas", "embeddings"])

                    if data["ids"]:
                        backup_data["collections"][s] = {
                            "ids": data["ids"],
                            "documents": data["documents"],
                            "metadatas": data["metadatas"],
                            # Embeddings are lists of floats, store them too for full restore
                            "embeddings": data["embeddings"] if data.get("embeddings") else []
                        }
                        total_memories += len(data["ids"])
                except Exception as e:
                    backup_data["collections"][s] = {"error": str(e)}

            # Write backup file
            with open(output_path, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)

            file_size = os.path.getsize(output_path)
            size_str = f"{file_size / 1024:.1f} KB" if file_size > 1024 else f"{file_size} bytes"

            output = f"✅ Backup completed!\n\n"
            output += f"**File:** {output_path}\n"
            output += f"**Size:** {size_str}\n"
            output += f"**Memories:** {total_memories}\n"
            output += f"**Scope:** {scope}\n"

            for s, data in backup_data["collections"].items():
                if "error" in data:
                    output += f"  ⚠️  {s}: {data['error']}\n"
                else:
                    output += f"  📁 {s}: {len(data['ids'])} memories\n"

            return [TextContent(type="text", text=output)]

        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_restore":
        input_path = arguments.get("input_path", "")
        mode = arguments.get("mode", "merge")
        target_scope = arguments.get("scope")

        if not input_path:
            return [TextContent(type="text", text="Error: input_path is required")]

        input_path = os.path.expanduser(input_path)

        if not os.path.exists(input_path):
            return [TextContent(type="text", text=f"Error: File not found: {input_path}")]

        try:
            # Load backup file
            with open(input_path, 'r') as f:
                backup_data = json.load(f)

            # Validate backup format
            if "version" not in backup_data or "collections" not in backup_data:
                return [TextContent(type="text", text="Error: Invalid backup format")]

            output = f"🔄 Restoring from backup...\n\n"
            output += f"**Backup date:** {backup_data.get('created_at', 'unknown')}\n"
            output += f"**Mode:** {mode}\n\n"

            total_restored = 0
            total_skipped = 0

            for scope_name, data in backup_data["collections"].items():
                if "error" in data:
                    output += f"⚠️  Skipping {scope_name}: backup had error\n"
                    continue

                # Use target_scope if specified, otherwise use original scope
                restore_scope = target_scope if target_scope else scope_name

                try:
                    coll = get_collection(restore_scope)

                    # If replace mode, clear existing data
                    if mode == "replace":
                        existing = coll.get()
                        if existing["ids"]:
                            coll.delete(ids=existing["ids"])
                            output += f"🗑️  Cleared {len(existing['ids'])} existing memories from {restore_scope}\n"

                    # Restore memories
                    ids = data.get("ids", [])
                    documents = data.get("documents", [])
                    metadatas = data.get("metadatas", [])
                    embeddings = data.get("embeddings", [])

                    if not ids:
                        output += f"⏭️  {scope_name}: No memories to restore\n"
                        continue

                    # Check for existing IDs in merge mode
                    if mode == "merge":
                        existing = coll.get(ids=ids)
                        existing_ids = set(existing["ids"]) if existing["ids"] else set()

                        # Filter out existing
                        new_indices = [i for i, id in enumerate(ids) if id not in existing_ids]

                        if len(new_indices) < len(ids):
                            total_skipped += len(ids) - len(new_indices)

                        if not new_indices:
                            output += f"⏭️  {scope_name} → {restore_scope}: All {len(ids)} memories already exist\n"
                            continue

                        ids = [ids[i] for i in new_indices]
                        documents = [documents[i] for i in new_indices]
                        metadatas = [metadatas[i] for i in new_indices]
                        if embeddings:
                            embeddings = [embeddings[i] for i in new_indices]

                    # Restore with embeddings if available, otherwise regenerate
                    if embeddings and len(embeddings) == len(ids):
                        coll.upsert(
                            ids=ids,
                            documents=documents,
                            metadatas=metadatas,
                            embeddings=embeddings
                        )
                    else:
                        # Need to regenerate embeddings
                        for i, (doc_id, doc, meta) in enumerate(zip(ids, documents, metadatas)):
                            embedding = get_embedding(doc)
                            coll.upsert(
                                ids=[doc_id],
                                documents=[doc],
                                metadatas=[meta],
                                embeddings=[embedding]
                            )

                    total_restored += len(ids)
                    output += f"✅ {scope_name} → {restore_scope}: {len(ids)} memories restored\n"

                except Exception as e:
                    output += f"❌ {scope_name}: {str(e)}\n"

            output += f"\n**Total restored:** {total_restored}"
            if total_skipped:
                output += f" (skipped {total_skipped} duplicates)"

            return [TextContent(type="text", text=output)]

        except json.JSONDecodeError:
            return [TextContent(type="text", text="Error: Invalid JSON file")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "rag_export":
        export_format = arguments.get("format", "agents")
        scope = arguments.get("scope", SCOPE_ALL)
        memory_types = arguments.get("memory_types", [])
        output_path = arguments.get("output_path", "")
        create_symlinks = arguments.get("create_symlinks", False)
        max_entries = arguments.get("max_entries", 50)

        # Format mapping
        FORMAT_FILES = {
            "agents": "AGENTS.md",
            "claude": "CLAUDE.md",
            "gemini": "GEMINI.md",
            "aider": "CONVENTIONS.md",
            "cursor": ".cursor/rules/project.mdc"
        }

        # Memory type display order and section names
        SECTION_ORDER = ["decision", "architecture", "preference", "bugfix", "snippet", "context"]
        SECTION_NAMES = {
            "decision": "Decisions",
            "architecture": "Architecture",
            "preference": "Preferences",
            "bugfix": "Bug Fixes",
            "snippet": "Code Snippets",
            "context": "Context"
        }

        try:
            # Collect memories from all relevant scopes
            all_memories = {}  # memory_type -> list of (doc, meta)

            for mem_type in SECTION_ORDER:
                if memory_types and mem_type not in memory_types:
                    continue
                all_memories[mem_type] = []

            scopes_to_check = [SCOPE_PROJECT, SCOPE_GLOBAL] if scope == SCOPE_ALL else [scope]

            for s in scopes_to_check:
                try:
                    coll = get_collection(s)
                    all_data = coll.get(include=["documents", "metadatas"])

                    if not all_data["documents"]:
                        continue

                    for doc, meta in zip(all_data["documents"], all_data["metadatas"]):
                        mem_type = meta.get("memory_type", "context")
                        if mem_type not in all_memories:
                            if not memory_types:  # Include if no filter
                                all_memories[mem_type] = []
                            else:
                                continue
                        meta["_scope"] = s
                        all_memories[mem_type].append((doc, meta))
                except Exception:
                    continue

            # Build markdown content
            lines = []

            # Header based on format
            if export_format == "agents":
                lines.append("# AGENTS.md")
                lines.append("")
                lines.append("> Universal context file for AI coding agents")
                lines.append("> Compatible with: Claude Code, Codex CLI, Gemini CLI, OpenCode, Aider, Cursor")
                lines.append("")
            elif export_format == "claude":
                lines.append("# CLAUDE.md")
                lines.append("")
                lines.append("> Context file for Claude Code")
                lines.append("")
            elif export_format == "gemini":
                lines.append("# GEMINI.md")
                lines.append("")
                lines.append("> Context file for Gemini CLI")
                lines.append("")
            elif export_format == "aider":
                lines.append("# CONVENTIONS.md")
                lines.append("")
                lines.append("> Coding conventions for Aider")
                lines.append("")
            elif export_format == "cursor":
                lines.append("# Project Rules")
                lines.append("")
                lines.append("> Auto-generated from RAG memory")
                lines.append("")

            lines.append(f"*Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
            lines.append("")
            lines.append("---")
            lines.append("")

            total_entries = 0
            for mem_type in SECTION_ORDER:
                if mem_type not in all_memories:
                    continue
                memories = all_memories[mem_type]
                if not memories:
                    continue

                # Sort by indexed_at (most recent first)
                memories.sort(key=lambda x: x[1].get("indexed_at", ""), reverse=True)
                memories = memories[:max_entries]

                section_name = SECTION_NAMES.get(mem_type, mem_type.title())
                lines.append(f"## {section_name}")
                lines.append("")

                for doc, meta in memories:
                    scope_icon = "🌐" if meta.get("_scope") == "global" else "📁"
                    source = meta.get("source", "")
                    if source.startswith("session:"):
                        source = "session"
                    elif source == "manual":
                        source = "manual"
                    else:
                        source = Path(source).name if source else ""

                    # Truncate long entries
                    content = doc.strip()
                    if len(content) > 500:
                        content = content[:500] + "..."

                    # Format as bullet or blockquote based on type
                    if mem_type == "snippet":
                        lines.append(f"### {source or 'Snippet'}")
                        lines.append("```")
                        lines.append(content)
                        lines.append("```")
                    elif mem_type in ("decision", "bugfix"):
                        lines.append(f"- {scope_icon} **{source}**: {content}")
                    else:
                        lines.append(f"- {scope_icon} {content}")

                    lines.append("")
                    total_entries += 1

                lines.append("")

            # Determine output path
            if output_path:
                out_path = Path(os.path.expanduser(output_path))
            else:
                out_path = Path(PROJECT_PATH) / FORMAT_FILES[export_format]

            # PROTECTION: Refuse to overwrite source files that are indexed
            # This prevents the bug where export overwrites CLAUDE.md
            sync_state = get_sync_state()
            out_path_str = str(out_path.resolve())
            for state_key in sync_state:
                if state_key.endswith(out_path_str):
                    return [TextContent(
                        type="text",
                        text=f"❌ Error: Cannot export to '{out_path}' - this file is indexed as a source.\n\n"
                             f"This would overwrite your source file and cause data loss!\n\n"
                             f"**Solutions:**\n"
                             f"1. Use a different output file: `output_path=\"AGENTS.md\"`\n"
                             f"2. Use 'agents' format instead of 'claude'\n"
                             f"3. Manually delete the file from sync state if you really want to overwrite"
                    )]

            # Create parent dirs if needed (for cursor format)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Backup existing file if it exists (prevent data loss!)
            backup_path = None
            if out_path.exists():
                backup_path = out_path.with_suffix(out_path.suffix + ".bak")
                # Keep only latest backup
                if backup_path.exists():
                    backup_path.unlink()
                out_path.rename(backup_path)

            # Write file
            out_path.write_text("\n".join(lines))

            # Create symlinks if requested (in same directory as output file)
            symlinks_created = []
            if create_symlinks and export_format == "agents":
                link_dir = out_path.parent
                for other_format, filename in FORMAT_FILES.items():
                    if other_format == "agents" or other_format == "cursor":
                        continue
                    link_path = link_dir / filename
                    try:
                        if link_path.exists() or link_path.is_symlink():
                            link_path.unlink()
                        link_path.symlink_to(out_path.name)
                        symlinks_created.append(filename)
                    except OSError:
                        pass  # Skip if can't create symlink

            output = f"✅ Exported {total_entries} memories to {out_path}\n"
            output += f"   Format: {export_format} ({FORMAT_FILES[export_format]})\n"
            output += f"   Scope: {scope}\n"

            if backup_path:
                output += f"   ⚠️  Backup created: {backup_path}\n"

            if symlinks_created:
                output += f"   Symlinks created: {', '.join(symlinks_created)}\n"

            return [TextContent(type="text", text=output)]

        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
