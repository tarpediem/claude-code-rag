#!/usr/bin/env python3
"""
Claude Code RAG - Web UI
Modern dashboard with FastAPI + HTMX
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime
from string import Template
from typing import Optional

from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# Add project root to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# Import RAG functions
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

CHROMA_PATH = os.environ.get("CHROMA_PATH", "~/.local/share/claude-memory")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
PROJECT_PATH = os.getcwd()

# Security constants
VALID_SCOPES = {"all", "project", "global"}
VALID_MEMORY_TYPES = {"context", "decision", "bugfix", "architecture", "preference", "snippet", "markdown", "python", "text"}
MAX_QUERY_LENGTH = 5000
MAX_RESULTS = 100

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_project_id() -> str:
    """Generate project ID from current working directory"""
    import hashlib
    return hashlib.sha256(PROJECT_PATH.encode()).hexdigest()[:12]


def get_db_path(scope: str) -> str:
    """Get database path for a scope (matches mcp_server.py structure)"""
    chroma_base = os.path.expanduser(CHROMA_PATH)
    if scope == "global":
        return os.path.join(chroma_base, "global")
    else:
        project_id = get_project_id()
        return os.path.join(chroma_base, project_id)


def get_collection(scope: str = "project"):
    """Get ChromaDB collection (matches mcp_server.py structure)"""
    if not CHROMA_AVAILABLE:
        return None

    db_path = get_db_path(scope)
    if not os.path.exists(db_path):
        return None

    try:
        client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        return client.get_collection("memories")
    except Exception:
        return None


def get_embedding(text: str) -> list:
    """Get embedding from Ollama"""
    import requests
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text},
        timeout=30
    )
    return resp.json().get("embedding", [])


def search_memories(query: str, scope: str = "all", n_results: int = 20, memory_type: str = None) -> list:
    """Search memories"""
    results = []
    scopes = ["project", "global"] if scope == "all" else [scope]

    query_embedding = get_embedding(query)
    if not query_embedding:
        return []

    for s in scopes:
        collection = get_collection(s)
        if not collection:
            continue

        try:
            where = {"memory_type": memory_type} if memory_type else None
            search_results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )

            for i, doc in enumerate(search_results["documents"][0]):
                meta = search_results["metadatas"][0][i]
                distance = search_results["distances"][0][i]
                results.append({
                    "id": search_results["ids"][0][i],
                    "content": doc,
                    "type": meta.get("memory_type") or meta.get("type", "context"),
                    "source": meta.get("source", "unknown"),
                    "scope": s,
                    "score": 1 - distance,  # Convert distance to similarity
                })
        except Exception:
            pass

    return sorted(results, key=lambda x: x["score"], reverse=True)[:n_results]


def get_all_memories(scope: str = "all", memory_type: str = None, limit: int = 100) -> list:
    """Get all memories"""
    results = []
    scopes = ["project", "global"] if scope == "all" else [scope]

    for s in scopes:
        collection = get_collection(s)
        if not collection:
            continue

        try:
            where = {"memory_type": memory_type} if memory_type else None
            data = collection.get(
                where=where,
                include=["documents", "metadatas"],
                limit=limit
            )

            for i, doc in enumerate(data["documents"]):
                meta = data["metadatas"][i]
                results.append({
                    "id": data["ids"][i],
                    "content": doc,
                    "type": meta.get("memory_type") or meta.get("type", "context"),
                    "source": meta.get("source", "unknown"),
                    "scope": s,
                })
        except Exception:
            pass

    return results[:limit]


def get_stats() -> dict:
    """Get RAG statistics"""
    stats = {
        "project_count": 0,
        "global_count": 0,
        "total_count": 0,
        "type_counts": {},
        "source_counts": {},
    }

    for scope in ["project", "global"]:
        collection = get_collection(scope)
        if not collection:
            continue

        try:
            count = collection.count()
            if scope == "project":
                stats["project_count"] = count
            else:
                stats["global_count"] = count

            # Get type breakdown
            data = collection.get(include=["metadatas"])
            for meta in data.get("metadatas", []):
                mem_type = meta.get("memory_type") or meta.get("type", "context")
                stats["type_counts"][mem_type] = stats["type_counts"].get(mem_type, 0) + 1

                source = Path(meta.get("source", "unknown")).name
                stats["source_counts"][source] = stats["source_counts"].get(source, 0) + 1
        except Exception:
            pass

    stats["total_count"] = stats["project_count"] + stats["global_count"]
    return stats


def delete_memory(memory_id: str, scope: str = "project") -> bool:
    """Delete a memory by ID"""
    collection = get_collection(scope)
    if not collection:
        return False

    try:
        collection.delete(ids=[memory_id])
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="Claude Code RAG", description="Semantic Memory Dashboard")

# HTML Templates inline (no external files needed)
HTML_BASE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Code RAG - Neural Dashboard</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
    <style>
        :root {
            --neon-cyan: #00f2ff;
            --neon-indigo: #6366f1;
            --deep-bg: #030014;
            --glass-dark: rgba(10, 10, 18, 0.45);
            --glass-border: rgba(255, 255, 255, 0.08);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        /* Layout */
        .app {
            display: grid;
            grid-template-columns: 240px 1fr;
            min-height: 100vh;
        }

        /* Sidebar with glassmorphism */
        .sidebar {
            background: var(--bg-sidebar);
            backdrop-filter: blur(20px) saturate(180%);
            -webkit-backdrop-filter: blur(20px) saturate(180%);
            border-right: 1px solid rgba(0, 0, 0, 0.06);
            padding: 2rem 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 2rem;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
            text-decoration: none;
        }

        .logo-icon {
            font-size: 1.5rem;
        }

        .nav {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .nav-item {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.6rem 0.875rem;
            border-radius: 10px;
            color: var(--text-secondary);
            text-decoration: none;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            font-size: 0.9375rem;
            font-weight: 500;
        }

        .nav-item:hover {
            background: rgba(0, 122, 255, 0.08);
            color: var(--accent-blue);
        }

        .nav-item.active {
            background: var(--accent-blue);
            color: white;
            box-shadow: 0 2px 8px rgba(0, 122, 255, 0.3);
        }

        /* Stats cards in sidebar */
        .stat-mini {
            background: var(--bg-secondary);
            border-radius: var(--radius);
            padding: 1.25rem;
            box-shadow: var(--shadow-sm);
        }

        .stat-mini-value {
            font-size: 2rem;
            font-weight: 600;
            color: var(--accent-blue);
            letter-spacing: -0.03em;
        }

        .stat-mini-label {
            font-size: 0.8125rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
        }

        /* Main content */
        .main {
            padding: 3rem;
            overflow-y: auto;
            max-width: 1400px;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
        }

        .header h1 {
            font-size: 1.75rem;
            font-weight: 600;
        }

        /* Search */
        .search-container {
            position: relative;
            margin-bottom: 2rem;
        }

        .search-input {
            width: 100%;
            padding: 0.875rem 1rem 0.875rem 2.75rem;
            background: var(--bg-secondary);
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: var(--radius);
            color: var(--text-primary);
            font-size: 1rem;
            box-shadow: var(--shadow-sm);
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .search-input:focus {
            outline: none;
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 4px rgba(0, 122, 255, 0.12), var(--shadow-md);
        }

        .search-icon {
            position: absolute;
            left: 1rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-secondary);
        }

        /* Cards */
        .card {
            background: var(--bg-secondary);
            border: 1px solid rgba(0, 0, 0, 0.06);
            border-radius: var(--radius-lg);
            padding: 1.75rem;
            margin-bottom: 1.25rem;
            box-shadow: var(--shadow-sm);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .card:hover {
            box-shadow: var(--shadow-md);
            transform: translateY(-2px);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1rem;
        }

        .card-meta {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 0.375rem;
            padding: 0.375rem 0.875rem;
            border-radius: 100px;
            font-size: 0.8125rem;
            font-weight: 600;
            letter-spacing: -0.01em;
        }

        .badge-type {
            background: rgba(175, 82, 222, 0.12);
            color: var(--accent-purple);
        }

        .badge-scope {
            background: rgba(52, 199, 89, 0.12);
            color: var(--accent-green);
        }

        .badge-score {
            background: rgba(255, 149, 0, 0.12);
            color: var(--accent-orange);
        }

        .card-content {
            color: var(--text-secondary);
            font-size: 0.95rem;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .card-footer {
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }

        /* Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.625rem 1.25rem;
            border-radius: 10px;
            border: none;
            font-size: 0.9375rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            letter-spacing: -0.01em;
        }

        .btn-primary {
            background: var(--accent-blue);
            color: white;
            box-shadow: 0 1px 4px rgba(0, 122, 255, 0.3);
        }

        .btn-primary:hover {
            background: #0062cc;
            box-shadow: 0 4px 12px rgba(0, 122, 255, 0.4);
            transform: translateY(-1px);
        }

        .btn-danger {
            background: rgba(255, 59, 48, 0.1);
            color: var(--accent-red);
            border: none;
        }

        .btn-danger:hover {
            background: var(--accent-red);
            color: white;
            box-shadow: 0 2px 8px rgba(255, 59, 48, 0.3);
        }

        .btn-ghost {
            background: transparent;
            color: var(--text-secondary);
        }

        .btn-ghost:hover {
            background: rgba(0, 0, 0, 0.04);
            color: var(--text-primary);
        }

        /* Stats grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2.5rem;
        }

        .stat-card {
            background: var(--bg-secondary);
            border: 1px solid rgba(0, 0, 0, 0.06);
            border-radius: var(--radius-lg);
            padding: 2rem 1.75rem;
            text-align: center;
            box-shadow: var(--shadow-sm);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .stat-card:hover {
            box-shadow: var(--shadow-md);
            transform: translateY(-2px);
        }

        .stat-value {
            font-size: 3rem;
            font-weight: 700;
            color: var(--accent-blue);
            letter-spacing: -0.05em;
        }

        .stat-label {
            color: var(--text-secondary);
            margin-top: 0.75rem;
            font-size: 0.9375rem;
            font-weight: 500;
        }

        /* Type breakdown */
        .type-list {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .type-item {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .type-name {
            width: 120px;
            color: var(--text-secondary);
        }

        .type-bar {
            flex: 1;
            height: 8px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            overflow: hidden;
        }

        .type-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple));
            border-radius: 4px;
            transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .type-count {
            width: 50px;
            text-align: right;
            color: var(--text-primary);
        }

        /* Filter pills */
        .filters {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin-bottom: 2rem;
        }

        .filter-pill {
            padding: 0.625rem 1.125rem;
            background: var(--bg-secondary);
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 100px;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            text-decoration: none;
            font-size: 0.9375rem;
            font-weight: 600;
            box-shadow: var(--shadow-sm);
        }

        .filter-pill:hover {
            background: rgba(0, 122, 255, 0.08);
            border-color: var(--accent-blue);
            color: var(--accent-blue);
            transform: translateY(-1px);
            box-shadow: var(--shadow-md);
        }

        .filter-pill.active {
            background: var(--accent-blue);
            border-color: var(--accent-blue);
            color: white;
            box-shadow: 0 2px 8px rgba(0, 122, 255, 0.3);
        }

        /* Empty state */
        .empty-state {
            text-align: center;
            padding: 3rem;
            color: var(--text-secondary);
        }

        .empty-state-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
        }

        /* HTMX loading indicator */
        .htmx-indicator {
            display: none;
        }

        .htmx-request .htmx-indicator {
            display: inline-block;
        }

        .htmx-request.htmx-indicator {
            display: inline-block;
        }

        /* Animations */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .card {
            animation: fadeIn 0.2s ease-out;
        }

        /* Responsive */
        @media (max-width: 1024px) {
            .main {
                padding: 2rem;
            }
            .stats-grid {
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            }
        }

        @media (max-width: 768px) {
            .app {
                grid-template-columns: 1fr;
            }
            .sidebar {
                position: fixed;
                left: -240px;
                top: 0;
                height: 100vh;
                z-index: 1000;
                transition: left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
            .sidebar.open {
                left: 0;
                box-shadow: var(--shadow-lg);
            }
            .main {
                padding: 1.5rem;
            }
            .header h1 {
                font-size: 1.5rem;
            }
            .stats-grid {
                grid-template-columns: 1fr;
            }
            .stat-card {
                padding: 1.5rem;
            }
            .stat-value {
                font-size: 2.25rem;
            }
        }

        @media (max-width: 480px) {
            .main {
                padding: 1rem;
            }
            .card {
                padding: 1.25rem;
            }
        }
    </style>
</head>
<body>
    <div class="app">
        <aside class="sidebar">
            <a href="/" class="logo">
                <span class="logo-icon">🧠</span>
                <span>Claude RAG</span>
            </a>

            <nav class="nav">
                <a href="/" class="nav-item $active_home">
                    <span>📊</span> Dashboard
                </a>
                <a href="/search" class="nav-item $active_search">
                    <span>🔍</span> Search
                </a>
                <a href="/memories" class="nav-item $active_memories">
                    <span>📚</span> Memories
                </a>
                <a href="/index" class="nav-item $active_index">
                    <span>📁</span> Index
                </a>
            </nav>

            <div class="stat-mini">
                <div class="stat-mini-value">$total_count</div>
                <div class="stat-mini-label">Total Memories</div>
            </div>
        </aside>

        <main class="main">
            $content
        </main>
    </div>
</body>
</html>
"""


def render_page(content: str, active: str = "", stats: dict = None) -> str:
    """Render a page with the base template"""
    if stats is None:
        stats = get_stats()

    return Template(HTML_BASE).safe_substitute(
        content=content,
        total_count=stats["total_count"],
        active_home="active" if active == "home" else "",
        active_search="active" if active == "search" else "",
        active_memories="active" if active == "memories" else "",
        active_index="active" if active == "index" else "",
    )


def render_memory_card(memory: dict, show_delete: bool = True) -> str:
    """Render a single memory card"""
    type_icons = {
        "decision": "🎯",
        "bugfix": "🐛",
        "architecture": "🏗️",
        "preference": "⚙️",
        "snippet": "📝",
        "context": "📄",
        "markdown": "📑",
        "python": "🐍",
        "text": "📃",
    }
    icon = type_icons.get(memory["type"], "💭")
    content = memory["content"][:500] + "..." if len(memory["content"]) > 500 else memory["content"]
    score_badge = f'<span class="badge badge-score">Score: {memory.get("score", 0):.2f}</span>' if "score" in memory else ""

    delete_btn = f'''
        <button class="btn btn-danger"
                hx-delete="/api/memories/{memory['id']}?scope={memory['scope']}"
                hx-confirm="Delete this memory?"
                hx-target="closest .card"
                hx-swap="outerHTML">
            🗑️ Delete
        </button>
    ''' if show_delete else ""

    return f'''
    <div class="card">
        <div class="card-header">
            <div class="card-meta">
                <span class="badge badge-type">{icon} {memory["type"]}</span>
                <span class="badge badge-scope">{"📁" if memory["scope"] == "project" else "🌐"} {memory["scope"]}</span>
                {score_badge}
            </div>
        </div>
        <div class="card-content">{content}</div>
        <div class="card-footer">
            <span>📄 {Path(memory["source"]).name}</span>
            {delete_btn}
        </div>
    </div>
    '''


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Dashboard page"""
    stats = get_stats()

    # Type breakdown
    type_bars = ""
    max_count = max(stats["type_counts"].values()) if stats["type_counts"] else 1
    for mem_type, count in sorted(stats["type_counts"].items(), key=lambda x: -x[1]):
        pct = int((count / max_count) * 100)
        type_bars += f'''
        <div class="type-item">
            <span class="type-name">{mem_type}</span>
            <div class="type-bar"><div class="type-bar-fill" style="width: {pct}%"></div></div>
            <span class="type-count">{count}</span>
        </div>
        '''

    content = f'''
    <div class="header">
        <h1>📊 Dashboard</h1>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value">{stats["total_count"]}</div>
            <div class="stat-label">Total Memories</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color: var(--accent-green)">{stats["project_count"]}</div>
            <div class="stat-label">📁 Project</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color: var(--accent-purple)">{stats["global_count"]}</div>
            <div class="stat-label">🌐 Global</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color: var(--accent-orange)">{len(stats["type_counts"])}</div>
            <div class="stat-label">Memory Types</div>
        </div>
    </div>

    <div class="card">
        <h3 style="margin-bottom: 1rem;">Memory Types</h3>
        <div class="type-list">
            {type_bars or '<div class="empty-state">No memories yet</div>'}
        </div>
    </div>
    '''

    return render_page(content, active="home", stats=stats)


@app.get("/search", response_class=HTMLResponse)
async def search_page(q: str = "", type: str = "", scope: str = "all"):
    """Search page"""
    results_html = ""

    if q:
        memories = search_memories(q, scope=scope, memory_type=type or None)
        if memories:
            for mem in memories:
                results_html += render_memory_card(mem)
        else:
            results_html = '''
            <div class="empty-state">
                <div class="empty-state-icon">🔍</div>
                <p>No results found</p>
            </div>
            '''
    else:
        results_html = '''
        <div class="empty-state">
            <div class="empty-state-icon">💡</div>
            <p>Enter a search query to find memories</p>
        </div>
        '''

    content = f'''
    <div class="header">
        <h1>🔍 Search</h1>
    </div>

    <div class="search-container">
        <span class="search-icon">🔍</span>
        <input type="text"
               class="search-input"
               placeholder="Search memories..."
               name="q"
               value="{q}"
               hx-get="/api/search"
               hx-trigger="keyup changed delay:300ms"
               hx-target="#results"
               hx-include="[name='scope'],[name='type']">
    </div>

    <div class="filters">
        <select name="scope" class="filter-pill" hx-get="/api/search" hx-trigger="change" hx-target="#results" hx-include="[name='q'],[name='type']">
            <option value="all" {"selected" if scope == "all" else ""}>All Scopes</option>
            <option value="project" {"selected" if scope == "project" else ""}>📁 Project</option>
            <option value="global" {"selected" if scope == "global" else ""}>🌐 Global</option>
        </select>
        <select name="type" class="filter-pill" hx-get="/api/search" hx-trigger="change" hx-target="#results" hx-include="[name='q'],[name='scope']">
            <option value="" {"selected" if not type else ""}>All Types</option>
            <option value="decision" {"selected" if type == "decision" else ""}>🎯 Decision</option>
            <option value="bugfix" {"selected" if type == "bugfix" else ""}>🐛 Bugfix</option>
            <option value="architecture" {"selected" if type == "architecture" else ""}>🏗️ Architecture</option>
            <option value="preference" {"selected" if type == "preference" else ""}>⚙️ Preference</option>
            <option value="snippet" {"selected" if type == "snippet" else ""}>📝 Snippet</option>
            <option value="context" {"selected" if type == "context" else ""}>📄 Context</option>
        </select>
    </div>

    <div id="results">
        {results_html}
    </div>
    '''

    return render_page(content, active="search")


@app.get("/memories", response_class=HTMLResponse)
async def memories_page(type: str = "", scope: str = "all"):
    """Memories browser page"""
    memories = get_all_memories(scope=scope, memory_type=type or None, limit=50)

    memories_html = ""
    if memories:
        for mem in memories:
            memories_html += render_memory_card(mem)
    else:
        memories_html = '''
        <div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <p>No memories found</p>
        </div>
        '''

    stats = get_stats()
    type_pills = '<a href="/memories" class="filter-pill ' + ('active' if not type else '') + '">All</a>'
    for t in sorted(stats["type_counts"].keys()):
        type_pills += f'<a href="/memories?type={t}&scope={scope}" class="filter-pill {"active" if type == t else ""}">{t}</a>'

    content = f'''
    <div class="header">
        <h1>📚 Memories</h1>
    </div>

    <div class="filters">
        {type_pills}
    </div>

    <div class="filters">
        <a href="/memories?type={type}&scope=all" class="filter-pill {"active" if scope == "all" else ""}">All</a>
        <a href="/memories?type={type}&scope=project" class="filter-pill {"active" if scope == "project" else ""}">📁 Project</a>
        <a href="/memories?type={type}&scope=global" class="filter-pill {"active" if scope == "global" else ""}">🌐 Global</a>
    </div>

    <div id="memories-list">
        {memories_html}
    </div>
    '''

    return render_page(content, active="memories")


@app.get("/index", response_class=HTMLResponse)
async def index_page():
    """Index page"""
    content = '''
    <div class="header">
        <h1>📁 Index Files</h1>
    </div>

    <div class="card">
        <h3 style="margin-bottom: 1rem;">Index a file or directory</h3>
        <form hx-post="/api/index" hx-target="#index-result" hx-swap="innerHTML">
            <div style="margin-bottom: 1rem;">
                <input type="text" name="path" class="search-input" placeholder="~/path/to/file_or_directory" style="padding-left: 1rem;">
            </div>
            <div style="display: flex; gap: 1rem; margin-bottom: 1rem;">
                <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                    <input type="radio" name="scope" value="project" checked> 📁 Project
                </label>
                <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                    <input type="radio" name="scope" value="global"> 🌐 Global
                </label>
            </div>
            <button type="submit" class="btn btn-primary">
                <span class="htmx-indicator">⏳</span>
                Index
            </button>
        </form>
        <div id="index-result" style="margin-top: 1rem;"></div>
    </div>
    '''

    return render_page(content, active="index")


# ═══════════════════════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/search", response_class=HTMLResponse)
async def api_search(q: str = "", type: str = "", scope: str = "all"):
    """Search API endpoint (returns HTML for HTMX)"""
    # Security: validate inputs
    if scope not in VALID_SCOPES:
        scope = "all"
    if type and type not in VALID_MEMORY_TYPES:
        type = ""
    if len(q) > MAX_QUERY_LENGTH:
        q = q[:MAX_QUERY_LENGTH]

    if not q:
        return '''
        <div class="empty-state">
            <div class="empty-state-icon">💡</div>
            <p>Enter a search query to find memories</p>
        </div>
        '''

    memories = search_memories(q, scope=scope, memory_type=type or None)

    if not memories:
        return '''
        <div class="empty-state">
            <div class="empty-state-icon">🔍</div>
            <p>No results found</p>
        </div>
        '''

    html = ""
    for mem in memories:
        html += render_memory_card(mem)
    return html


@app.delete("/api/memories/{memory_id}", response_class=HTMLResponse)
async def api_delete_memory(memory_id: str, scope: str = "project"):
    """Delete a memory"""
    # Security: validate scope
    if scope not in {"project", "global"}:
        raise HTTPException(status_code=400, detail="Invalid scope")

    # Security: validate memory_id format (alphanumeric + dash/underscore)
    if not memory_id or not all(c.isalnum() or c in "-_" for c in memory_id):
        raise HTTPException(status_code=400, detail="Invalid memory ID")

    success = delete_memory(memory_id, scope)
    if success:
        return ""  # Empty response removes the element
    raise HTTPException(status_code=404, detail="Memory not found")


@app.post("/api/index", response_class=HTMLResponse)
async def api_index(path: str = Form(...), scope: str = Form("project")):
    """Index a file or directory"""
    import subprocess

    # Security: validate scope
    if scope not in {"project", "global"}:
        return '<div style="color: var(--accent-red);">❌ Invalid scope</div>'

    expanded_path = os.path.expanduser(path)

    # Security: basic path validation
    if ".." in path or not expanded_path:
        return '<div style="color: var(--accent-red);">❌ Invalid path</div>'

    if not os.path.exists(expanded_path):
        return '<div style="color: var(--accent-red);">❌ Path not found or not accessible</div>'

    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "claude_rag.py"), "index", expanded_path, "--scope", scope],
            capture_output=True, text=True, timeout=120
        )
        output = result.stdout or result.stderr or "Done"
        return f'<div style="color: var(--accent-green);">✅ {output}</div>'
    except subprocess.TimeoutExpired:
        return '<div style="color: var(--accent-red);">❌ Indexing timeout</div>'
    except Exception:
        return '<div style="color: var(--accent-red);">❌ Indexing failed</div>'


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Run the web server"""
    import argparse

    parser = argparse.ArgumentParser(description="Claude Code RAG Web UI")
    parser.add_argument("-p", "--port", type=int, default=8420, help="Port (default: 8420)")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1, use 0.0.0.0 for network access)")
    args = parser.parse_args()

    # Security warning for network exposure
    if args.host == "0.0.0.0":
        print("⚠️  WARNING: Binding to 0.0.0.0 exposes the server to the network WITHOUT authentication!")
        print("⚠️  Only use this on trusted networks.")

    print("🌐 Starting Claude Code RAG Web UI...")
    print(f"📍 Open http://localhost:{args.port} in your browser")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
