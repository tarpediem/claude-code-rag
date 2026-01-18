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

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_chroma_client():
    """Get ChromaDB client"""
    if not CHROMA_AVAILABLE:
        return None
    return chromadb.PersistentClient(
        path=os.path.expanduser(CHROMA_PATH),
        settings=Settings(anonymized_telemetry=False)
    )


def get_collection(scope: str = "project"):
    """Get ChromaDB collection"""
    client = get_chroma_client()
    if not client:
        return None

    project_path = os.getcwd()
    if scope == "project":
        collection_name = f"claude_rag_project_{hash(project_path) % 10**8}"
    else:
        collection_name = f"claude_rag_{scope}"

    try:
        return client.get_collection(collection_name)
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
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Code RAG</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --border-color: #30363d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-purple: #a371f7;
            --accent-orange: #d29922;
            --accent-red: #f85149;
            --radius: 8px;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }

        /* Layout */
        .app {
            display: grid;
            grid-template-columns: 260px 1fr;
            min-height: 100vh;
        }

        /* Sidebar */
        .sidebar {
            background: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
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
            padding: 0.75rem 1rem;
            border-radius: var(--radius);
            color: var(--text-secondary);
            text-decoration: none;
            transition: all 0.15s;
        }

        .nav-item:hover, .nav-item.active {
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }

        .nav-item.active {
            border-left: 2px solid var(--accent-blue);
        }

        /* Stats cards in sidebar */
        .stat-mini {
            background: var(--bg-tertiary);
            border-radius: var(--radius);
            padding: 1rem;
        }

        .stat-mini-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--accent-blue);
        }

        .stat-mini-label {
            font-size: 0.8rem;
            color: var(--text-secondary);
        }

        /* Main content */
        .main {
            padding: 2rem;
            overflow-y: auto;
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
            padding: 1rem 1rem 1rem 3rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            color: var(--text-primary);
            font-size: 1rem;
        }

        .search-input:focus {
            outline: none;
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.2);
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
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 1.5rem;
            margin-bottom: 1rem;
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
            gap: 0.25rem;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
        }

        .badge-type {
            background: rgba(163, 113, 247, 0.2);
            color: var(--accent-purple);
        }

        .badge-scope {
            background: rgba(63, 185, 80, 0.2);
            color: var(--accent-green);
        }

        .badge-score {
            background: rgba(210, 153, 34, 0.2);
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
            padding: 0.5rem 1rem;
            border-radius: var(--radius);
            border: none;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
        }

        .btn-primary {
            background: var(--accent-blue);
            color: white;
        }

        .btn-primary:hover {
            background: #4c9aed;
        }

        .btn-danger {
            background: transparent;
            color: var(--accent-red);
            border: 1px solid var(--accent-red);
        }

        .btn-danger:hover {
            background: var(--accent-red);
            color: white;
        }

        .btn-ghost {
            background: transparent;
            color: var(--text-secondary);
        }

        .btn-ghost:hover {
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }

        /* Stats grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 1.5rem;
            text-align: center;
        }

        .stat-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--accent-blue);
        }

        .stat-label {
            color: var(--text-secondary);
            margin-top: 0.5rem;
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
            background: var(--accent-purple);
            border-radius: 4px;
        }

        .type-count {
            width: 50px;
            text-align: right;
            color: var(--text-primary);
        }

        /* Filter pills */
        .filters {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-bottom: 1.5rem;
        }

        .filter-pill {
            padding: 0.5rem 1rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.15s;
            text-decoration: none;
            font-size: 0.875rem;
        }

        .filter-pill:hover, .filter-pill.active {
            background: var(--accent-blue);
            border-color: var(--accent-blue);
            color: white;
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
        @media (max-width: 768px) {
            .app {
                grid-template-columns: 1fr;
            }
            .sidebar {
                display: none;
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
    success = delete_memory(memory_id, scope)
    if success:
        return ""  # Empty response removes the element
    raise HTTPException(status_code=404, detail="Memory not found")


@app.post("/api/index", response_class=HTMLResponse)
async def api_index(path: str = Form(...), scope: str = Form("project")):
    """Index a file or directory"""
    import subprocess

    expanded_path = os.path.expanduser(path)
    if not os.path.exists(expanded_path):
        return f'<div style="color: var(--accent-red);">❌ Path not found: {path}</div>'

    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "claude_rag.py"), "index", expanded_path, "--scope", scope],
            capture_output=True, text=True, timeout=120
        )
        output = result.stdout or result.stderr or "Done"
        return f'<div style="color: var(--accent-green);">✅ {output}</div>'
    except Exception as e:
        return f'<div style="color: var(--accent-red);">❌ Error: {e}</div>'


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Run the web server"""
    import argparse

    parser = argparse.ArgumentParser(description="Claude Code RAG Web UI")
    parser.add_argument("-p", "--port", type=int, default=8420, help="Port (default: 8420)")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    args = parser.parse_args()

    print("🌐 Starting Claude Code RAG Web UI...")
    print(f"📍 Open http://localhost:{args.port} in your browser")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
