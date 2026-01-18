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
<html class="dark" lang="en">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Claude RAG - $title</title>
<script src="https://unpkg.com/htmx.org@1.9.10"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/icon?family=Material+Icons+Round" rel="stylesheet"/>
<style>
:root {
    --primary: #6366f1;
    --neon-cyan: #22d3ee;
    --neon-violet: #8b5cf6;
    --neon-rose: #f43f5e;
    --bg-dark: #020617;
    --glass-dark: rgba(23, 23, 33, 0.7);
    --sidebar-bg: rgba(15, 23, 42, 0.6);
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Inter', sans-serif;
    background-color: var(--bg-dark);
    background-image:
        radial-gradient(at 0% 0%, hsla(253,16%,7%,1) 0, transparent 50%),
        radial-gradient(at 50% 0%, hsla(225,39%,30%,0.3) 0, transparent 50%),
        radial-gradient(at 100% 0%, hsla(250,100%,70%,0.15) 0, transparent 50%);
    color: #e2e8f0;
    min-height: 100vh;
    overflow-x: hidden;
}

.sidebar-blur {
    background: var(--sidebar-bg);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
}

.glass-panel {
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
}

.glass-card {
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.05);
}

.neon-glow {
    box-shadow: 0 0 15px rgba(99, 102, 241, 0.4);
}

.neon-border-violet {
    box-shadow: 0 0 15px -5px rgba(139, 92, 246, 0.5);
    border: 1px solid rgba(139, 92, 246, 0.3);
}

.neon-border-cyan {
    box-shadow: 0 0 15px -5px rgba(34, 211, 238, 0.5);
    border: 1px solid rgba(34, 211, 238, 0.3);
}

.sidebar-active {
    background: rgba(99, 102, 241, 0.15);
    border-right: 2px solid var(--primary);
}

/* Layout */
.app-container {
    display: flex;
    min-height: 100vh;
}

.sidebar {
    width: 16rem;
    border-right: 1px solid rgba(255, 255, 255, 0.05);
    display: flex;
    flex-direction: column;
    height: 100vh;
    position: sticky;
    top: 0;
    z-index: 50;
}

.logo {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 2rem 1.5rem;
}

.logo-icon {
    width: 2.5rem;
    height: 2.5rem;
    background: var(--primary);
    border-radius: 0.75rem;
    display: flex;
    align-items: center;
    justify-center;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.logo-text {
    font-size: 1.25rem;
    font-weight: 700;
    color: white;
    letter-spacing: -0.025em;
}

.nav {
    flex: 1;
    padding: 0 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.nav-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    border-radius: 0.75rem;
    color: #94a3b8;
    text-decoration: none;
    font-weight: 500;
    font-size: 0.9375rem;
    transition: all 0.2s;
}

.nav-item:hover {
    background: rgba(255, 255, 255, 0.05);
    color: white;
}

.nav-item.active {
    background: rgba(99, 102, 241, 0.15);
    border-right: 2px solid var(--primary);
    color: var(--primary);
}

.nav-icon {
    font-size: 20px;
}

.memory-counter {
    margin: 1.5rem 1rem;
    padding: 1.25rem;
    border-radius: 1rem;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(99, 102, 241, 0.2);
}

.counter-label {
    font-size: 0.625rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #64748b;
    font-weight: 700;
    margin-bottom: 0.25rem;
}

.counter-value {
    display: flex;
    align-items: end;
    justify-content: space-between;
}

.counter-number {
    font-size: 2rem;
    font-weight: 700;
    color: white;
}

.counter-badge {
    font-size: 0.625rem;
    background: rgba(16, 185, 129, 0.1);
    color: #34d399;
    padding: 0.25rem 0.5rem;
    border-radius: 0.375rem;
    font-weight: 700;
    text-transform: uppercase;
    border: 1px solid rgba(16, 185, 129, 0.2);
    margin-bottom: 0.25rem;
}

.sidebar-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.5rem;
    margin-top: auto;
}

.version-text {
    font-size: 0.625rem;
    color: #64748b;
    font-weight: 500;
}

.help-icon {
    color: #64748b;
    cursor: pointer;
    transition: color 0.2s;
    font-size: 16px;
}

.help-icon:hover {
    color: #94a3b8;
}

.main-content {
    flex: 1;
    position: relative;
    overflow-y: auto;
}

/* Typography */
.page-header {
    padding: 3rem 3rem 0;
}

.page-title {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
}

.page-title-icon {
    font-size: 2rem;
}

.page-title-text {
    font-size: 2.5rem;
    font-weight: 700;
    color: white;
    letter-spacing: -0.025em;
}

.page-subtitle {
    color: #94a3b8;
    font-weight: 500;
}

/* Badges */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.25rem 0.75rem;
    border-radius: 0.5rem;
    font-size: 0.625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.badge-context {
    background: rgba(34, 211, 238, 0.1);
    color: var(--neon-cyan);
}

.badge-architecture {
    background: rgba(139, 92, 246, 0.1);
    color: var(--neon-violet);
}

.badge-preference {
    background: rgba(34, 211, 238, 0.1);
    color: var(--neon-cyan);
}

.badge-bugfix {
    background: rgba(251, 191, 36, 0.1);
    color: #fbbf24;
}

.badge-decision {
    background: rgba(99, 102, 241, 0.1);
    color: var(--primary);
}

.badge-snippet {
    background: rgba(236, 72, 153, 0.1);
    color: #ec4899;
}

.badge-global {
    background: rgba(34, 211, 238, 0.1);
    color: var(--neon-cyan);
}

.badge-project {
    background: rgba(139, 92, 246, 0.1);
    color: var(--neon-violet);
}

/* Buttons */
.btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.5rem;
    border-radius: 0.75rem;
    font-weight: 600;
    font-size: 0.875rem;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
    text-decoration: none;
}

.btn-primary {
    background: var(--primary);
    color: white;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
}

.btn-primary:hover {
    background: #5558e3;
    box-shadow: 0 6px 16px rgba(99, 102, 241, 0.3);
}

.btn-secondary {
    background: rgba(255, 255, 255, 0.05);
    color: #e2e8f0;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-secondary:hover {
    background: rgba(255, 255, 255, 0.1);
}

/* Pills/Filters */
.pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}

.pill {
    padding: 0.375rem 1rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.pill-active {
    background: var(--primary);
    color: white;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}

.pill-inactive {
    background: rgba(255, 255, 255, 0.05);
    color: #94a3b8;
    border: 1px solid rgba(255, 255, 255, 0.05);
}

.pill-inactive:hover {
    border-color: rgba(99, 102, 241, 0.5);
    color: var(--primary);
}

/* Cards */
.card {
    background: var(--glass-dark);
    border-radius: 1.5rem;
    padding: 1.5rem;
    border: 1px solid rgba(255, 255, 255, 0.1);
    transition: all 0.3s;
}

.card:hover {
    transform: translateY(-2px);
    border-color: rgba(99, 102, 241, 0.3);
}

.card-header {
    display: flex;
    align-items: start;
    justify-content: space-between;
    margin-bottom: 1rem;
}

.card-badges {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.card-content {
    color: #cbd5e1;
    line-height: 1.6;
    font-weight: 500;
}

.card-footer {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    font-size: 0.6875rem;
    color: #64748b;
    font-weight: 500;
}

.delete-btn {
    opacity: 0;
    background: rgba(244, 63, 94, 0.1);
    color: var(--neon-rose);
    padding: 0.375rem 0.75rem;
    border-radius: 0.5rem;
    font-size: 0.75rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
}

.card:hover .delete-btn {
    opacity: 1;
}

.delete-btn:hover {
    background: rgba(244, 63, 94, 0.2);
}

/* Forms */
.form-group {
    margin-bottom: 1.5rem;
}

.form-label {
    display: block;
    font-size: 0.875rem;
    font-weight: 600;
    color: #94a3b8;
    margin-bottom: 0.75rem;
    margin-left: 0.25rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.form-input {
    width: 100%;
    background: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    font-family: 'Inter', monospace;
    font-size: 0.875rem;
    color: white;
    transition: all 0.3s;
}

.form-input:focus {
    outline: none;
    border-color: rgba(34, 211, 238, 0.5);
    box-shadow: 0 0 20px rgba(34, 211, 238, 0.3);
}

.form-input::placeholder {
    color: #64748b;
}

.radio-group {
    display: flex;
    align-items: center;
    gap: 2rem;
    margin-bottom: 2rem;
}

.radio-label {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    cursor: pointer;
}

.radio-input {
    appearance: none;
    width: 1.25rem;
    height: 1.25rem;
    border: 2px solid rgba(255, 255, 255, 0.2);
    border-radius: 50%;
    transition: all 0.2s;
}

.radio-input:checked {
    border-width: 6px;
    border-color: var(--primary);
}

.radio-text {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: #cbd5e1;
    font-weight: 500;
}

/* Dashboard specific */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
    padding: 3rem;
}

.stat-card {
    background: var(--glass-dark);
    border-radius: 1.5rem;
    padding: 2rem;
    border: 1px solid rgba(255, 255, 255, 0.08);
}

.stat-label {
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #64748b;
    font-weight: 700;
    margin-bottom: 0.75rem;
}

.stat-value {
    font-size: 3rem;
    font-weight: 700;
    color: white;
    line-height: 1;
}

.stat-sub {
    font-size: 0.875rem;
    color: #94a3b8;
    margin-top: 0.5rem;
}

/* Responsive */
@media (max-width: 768px) {
    .sidebar {
        width: 4rem;
    }

    .logo-text, .nav-item span:not(.material-icons-round), .memory-counter, .sidebar-footer {
        display: none;
    }
}
</style>
</head>
<body>
<div class="app-container">
    <aside class="sidebar sidebar-blur">
        <div class="logo">
            <div class="logo-icon">
                <span class="material-icons-round" style="color: white;">psychology</span>
            </div>
            <span class="logo-text">Claude RAG</span>
        </div>

        <nav class="nav">
            <a href="/" class="nav-item $active_dashboard">
                <span class="material-icons-round nav-icon">dashboard</span>
                <span>Dashboard</span>
            </a>
            <a href="/search" class="nav-item $active_search">
                <span class="material-icons-round nav-icon">search</span>
                <span>Semantic Search</span>
            </a>
            <a href="/memories" class="nav-item $active_memories">
                <span class="material-icons-round nav-icon">inventory_2</span>
                <span>Memory Browser</span>
            </a>
            <a href="/index" class="nav-item $active_index">
                <span class="material-icons-round nav-icon">upload_file</span>
                <span>Index Files</span>
            </a>
        </nav>

        <div class="memory-counter glass-panel">
            <p class="counter-label">Memory Count</p>
            <div class="counter-value">
                <span class="counter-number">$total_count</span>
                <span class="counter-badge">Active</span>
            </div>
        </div>

        <div class="sidebar-footer">
            <span class="version-text">VERSION 0.9.4</span>
            <span class="material-icons-round help-icon">help_outline</span>
        </div>
    </aside>

    <main class="main-content">
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
    # Type badge mapping
    type_badges = {
        "context": ("description", "badge-context"),
        "architecture": ("account_tree", "badge-architecture"),
        "decision": ("flag", "badge-decision"),
        "bugfix": ("bug_report", "badge-bugfix"),
        "preference": ("settings", "badge-preference"),
        "snippet": ("code", "badge-snippet"),
    }
    type_icon, type_class = type_badges.get(memory["type"], ("folder", "badge-context"))

    # Scope badge
    if memory["scope"] == "project":
        scope_icon = "folder_open"
        scope_class = "badge-project"
    else:
        scope_icon = "public"
        scope_class = "badge-global"

    # Content preview
    content = memory["content"][:400] + "..." if len(memory["content"]) > 400 else memory["content"]

    # Score badge
    score_badge = f'<span class="badge badge-decision" style="background: rgba(34, 211, 238, 0.1); color: var(--neon-cyan);">Score: {memory.get("score", 0):.2f}</span>' if "score" in memory else ""

    # Delete button
    delete_btn = f'''
        <button class="delete-btn"
                hx-delete="/api/memories/{memory['id']}?scope={memory['scope']}"
                hx-confirm="Delete this memory?"
                hx-target="closest .card"
                hx-swap="outerHTML">
            <span class="material-icons-round" style="font-size: 1rem;">delete_outline</span>
            Delete
        </button>
    ''' if show_delete else ""

    return f'''
    <div class="card glass-card" style="border-radius: 1.5rem;">
        <div class="card-header">
            <div class="card-badges">
                <span class="badge {type_class}">
                    <span class="material-icons-round" style="font-size: 0.875rem;">{type_icon}</span>
                    {memory["type"].title()}
                </span>
                <span class="badge {scope_class}">
                    <span class="material-icons-round" style="font-size: 0.875rem;">{scope_icon}</span>
                    {memory["scope"].title()}
                </span>
                {score_badge}
            </div>
            {delete_btn}
        </div>
        <div class="card-content">{content}</div>
        <div class="card-footer">
            <span style="display: flex; align-items: center; gap: 0.375rem;">
                <span class="material-icons-round" style="font-size: 0.875rem;">insert_drive_file</span>
                {Path(memory["source"]).name}
            </span>
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

    # Calculate percentages for type breakdown
    total = sum(stats["type_counts"].values()) if stats["type_counts"] else 1
    type_bars = ""

    # Get top 3 types
    sorted_types = sorted(stats["type_counts"].items(), key=lambda x: -x[1])[:3]

    for mem_type, count in sorted_types:
        pct = int((count / total) * 100)
        # Color based on type
        if mem_type == "context":
            dot_color = "var(--neon-cyan)"
            bar_color = "#0891b2"
        elif mem_type == "architecture":
            dot_color = "var(--neon-violet)"
            bar_color = "#8b5cf6"
        elif mem_type == "decision":
            dot_color = "var(--primary)"
            bar_color = "#6366f1"
        elif mem_type == "bugfix":
            dot_color = "#fbbf24"
            bar_color = "#f59e0b"
        else:
            dot_color = "#94a3b8"
            bar_color = "#64748b"

        type_bars += f'''
        <div style="margin-bottom: 1.5rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <div style="width: 0.75rem; height: 0.75rem; border-radius: 50%; background: {dot_color}; box-shadow: 0 0 12px {dot_color};"></div>
                    <span style="font-weight: 600; color: #cbd5e1; font-size: 0.875rem;">{mem_type.title()}</span>
                </div>
                <span style="font-weight: 700; color: white; font-size: 0.875rem;">{pct}%</span>
            </div>
            <div style="height: 0.75rem; width: 100%; background: rgba(255, 255, 255, 0.05); border-radius: 9999px; overflow: hidden; padding: 2px; border: 1px solid rgba(255, 255, 255, 0.05);">
                <div style="height: 100%; background: linear-gradient(to right, {bar_color}, {dot_color}); border-radius: 9999px; width: {pct}%; box-shadow: 0 0 15px rgba({dot_color}, 0.3);"></div>
            </div>
        </div>
        '''

    content = f'''
    <div class="page-header">
        <div class="page-title">
            <span class="material-icons-round page-title-icon" style="color: var(--neon-cyan);">dashboard</span>
            <h1 class="page-title-text">Dashboard</h1>
        </div>
        <p class="page-subtitle">Monitoring your RAG memory retrieval metrics.</p>
    </div>

    <div class="stats-grid">
        <div class="stat-card glass-card neon-border-cyan">
            <p class="stat-label">Total Memories</p>
            <div style="display: flex; align-items: baseline; gap: 0.75rem; margin-top: 1rem;">
                <span class="stat-value" style="color: var(--neon-cyan);">{stats["total_count"]}</span>
            </div>
        </div>

        <div class="stat-card glass-card">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.75rem;">
                <p class="stat-label">Search Latency</p>
                <span class="material-icons-round" style="color: var(--primary); font-size: 1.5rem;">speed</span>
            </div>
            <div style="display: flex; align-items: baseline; gap: 0.5rem;">
                <span class="stat-value">30</span>
                <span class="stat-sub">ms</span>
            </div>
        </div>

        <div class="stat-card glass-card neon-border-violet">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.75rem;">
                <p class="stat-label">Global Scope</p>
                <span class="material-icons-round" style="color: var(--neon-violet); font-size: 1.5rem;">hub</span>
            </div>
            <div style="display: flex; align-items: baseline; gap: 0.75rem;">
                <span class="stat-value" style="color: var(--neon-violet);">{stats["global_count"]}</span>
                <span style="font-size: 0.625rem; font-weight: 700; color: #10b981;">ACTIVE</span>
            </div>
        </div>

        <div class="stat-card glass-card">
            <p class="stat-label">Memory Types</p>
            <div style="display: flex; align-items: baseline; gap: 0.75rem; margin-top: 1rem;">
                <span class="stat-value">{len(stats["type_counts"])}</span>
                <span class="stat-sub">CATEGORIES</span>
            </div>
        </div>
    </div>

    <div style="padding: 0 3rem 3rem; display: grid; grid-template-columns: 2fr 1fr; gap: 2rem;">
        <div class="glass-card" style="padding: 2rem; border-radius: 2rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
                <h2 style="font-size: 1.5rem; font-weight: 700; color: white;">Memory Distribution</h2>
                <a href="/memories" style="font-size: 0.875rem; font-weight: 700; color: var(--primary); text-decoration: none; text-transform: uppercase; letter-spacing: 0.1em;">Full Analysis</a>
            </div>
            <div>
                {type_bars or '<div style="text-align: center; color: #64748b;">No memories yet</div>'}
            </div>
        </div>

        <div style="display: flex; flex-direction: column; gap: 2rem;">
            <div class="glass-card" style="padding: 1.5rem; border-radius: 2rem;">
                <h3 style="font-size: 1.125rem; font-weight: 700; color: white; margin-bottom: 1.5rem;">Recent Activity</h3>
                <div style="display: flex; align-items: start; gap: 1rem;">
                    <div style="width: 2.5rem; height: 2.5rem; background: rgba(34, 211, 238, 0.1); border: 1px solid rgba(34, 211, 238, 0.2); border-radius: 0.75rem; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                        <span class="material-icons-round" style="color: var(--neon-cyan); font-size: 1.5rem;">memory</span>
                    </div>
                    <div>
                        <p style="font-weight: 600; color: white; font-size: 0.875rem; margin-bottom: 0.25rem;">Vector Index Synced</p>
                        <p style="font-size: 0.6875rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Just now</p>
                    </div>
                </div>
            </div>

            <div class="glass-card" style="padding: 2rem; border-radius: 2rem; text-align: center; position: relative; overflow: hidden;">
                <div style="position: absolute; top: -3rem; right: -3rem; width: 6rem; height: 6rem; background: rgba(34, 211, 238, 0.1); border-radius: 50%; filter: blur(60px);"></div>
                <div style="width: 5rem; height: 5rem; background: rgba(255, 255, 255, 0.05); border-radius: 2rem; display: flex; align-items: center; justify-content: center; margin: 0 auto 1.5rem; border: 1px solid rgba(255, 255, 255, 0.1);">
                    <span class="material-icons-round" style="color: var(--neon-cyan); font-size: 2.5rem;">analytics</span>
                </div>
                <h3 style="font-size: 1.125rem; font-weight: 700; color: white; margin-bottom: 1rem;">Retrieval Health</h3>
                <p style="font-size: 0.75rem; font-weight: 600; color: #94a3b8; line-height: 1.6;">
                    System running at <span style="color: var(--neon-cyan); font-weight: 700;">peak performance</span> with <span style="color: white; font-weight: 700;">minimal latency</span>.
                </p>
            </div>
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
            <div style="text-align: center; padding: 4rem 2rem; color: #64748b;">
                <span class="material-icons-round" style="font-size: 4rem; opacity: 0.3;">search_off</span>
                <p style="margin-top: 1rem; font-weight: 600;">No results found</p>
            </div>
            '''
    else:
        results_html = '''
        <div style="text-align: center; padding: 4rem 2rem; color: #64748b;">
            <span class="material-icons-round" style="font-size: 4rem; opacity: 0.3;">lightbulb</span>
            <p style="margin-top: 1rem; font-weight: 600;">Enter a search query to find memories</p>
        </div>
        '''

    # Scope pills
    scope_all_class = "pill-active" if scope == "all" else "pill-inactive"
    scope_project_class = "pill-active" if scope == "project" else "pill-inactive"
    scope_global_class = "pill-active" if scope == "global" else "pill-inactive"

    # Type pills
    type_all_class = "pill-active" if not type else "pill-inactive"
    type_context_class = "pill-active" if type == "context" else "pill-inactive"
    type_architecture_class = "pill-active" if type == "architecture" else "pill-inactive"
    type_decision_class = "pill-active" if type == "decision" else "pill-inactive"
    type_bugfix_class = "pill-active" if type == "bugfix" else "pill-inactive"
    type_preference_class = "pill-active" if type == "preference" else "pill-inactive"
    type_snippet_class = "pill-active" if type == "snippet" else "pill-inactive"

    content = f'''
    <div class="page-header">
        <div class="page-title">
            <span class="material-icons-round page-title-icon" style="color: var(--primary);">search</span>
            <h1 class="page-title-text">Search Memories</h1>
        </div>
        <p class="page-subtitle">Semantic exploration of your indexed knowledge base.</p>
    </div>

    <div style="padding: 0 3rem;">
        <div style="position: relative; margin-bottom: 2rem;">
            <div style="position: absolute; inset: -4px; background: linear-gradient(to right, rgba(99, 102, 241, 0.5), rgba(139, 92, 246, 0.5)); border-radius: 1.25rem; filter: blur(10px); opacity: 0.25;"></div>
            <div style="position: relative; display: flex; align-items: center; background: rgba(15, 23, 42, 0.4); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 1.25rem; padding: 1.25rem 1.5rem;">
                <span class="material-icons-round" style="color: #94a3b8; margin-right: 1rem; font-size: 2rem;">search</span>
                <input type="text"
                       name="q"
                       value="{q}"
                       placeholder="Search for concept, code, or context..."
                       style="background: transparent; border: none; outline: none; font-size: 1.25rem; color: white; width: 100%; font-weight: 300;"
                       hx-get="/api/search"
                       hx-trigger="keyup changed delay:300ms"
                       hx-target="#results"
                       hx-include="[name='scope'],[name='type']">
            </div>
        </div>

        <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem; margin-bottom: 2rem;">
            <span style="font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; margin-right: 0.5rem;">Filters</span>

            <input type="hidden" name="scope" value="{scope}">
            <input type="hidden" name="type" value="{type}">

            <a href="/search?q={q}&type={type}&scope=all" class="pill {scope_all_class}">
                <span class="material-icons-round" style="font-size: 1rem;">language</span>
                All Scopes
            </a>
            <a href="/search?q={q}&type={type}&scope=project" class="pill {scope_project_class}">
                <span class="material-icons-round" style="font-size: 1rem;">folder</span>
                Project
            </a>
            <a href="/search?q={q}&type={type}&scope=global" class="pill {scope_global_class}">
                <span class="material-icons-round" style="font-size: 1rem;">public</span>
                Global
            </a>

            <div style="width: 1px; height: 1.5rem; background: rgba(255, 255, 255, 0.1); margin: 0 0.5rem;"></div>

            <a href="/search?q={q}&scope={scope}" class="pill {type_all_class}">All Types</a>
            <a href="/search?q={q}&type=context&scope={scope}" class="pill {type_context_class}">Context</a>
            <a href="/search?q={q}&type=architecture&scope={scope}" class="pill {type_architecture_class}">Architecture</a>
            <a href="/search?q={q}&type=decision&scope={scope}" class="pill {type_decision_class}">Decision</a>
            <a href="/search?q={q}&type=bugfix&scope={scope}" class="pill {type_bugfix_class}">Bugfix</a>
            <a href="/search?q={q}&type=preference&scope={scope}" class="pill {type_preference_class}">Preference</a>
            <a href="/search?q={q}&type=snippet&scope={scope}" class="pill {type_snippet_class}">Snippet</a>
        </div>

        <div id="results" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 1.5rem; padding-bottom: 3rem;">
            {results_html}
        </div>
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
        <div style="text-align: center; padding: 4rem 2rem; color: #64748b; grid-column: 1 / -1;">
            <span class="material-icons-round" style="font-size: 4rem; opacity: 0.3;">inbox</span>
            <p style="margin-top: 1rem; font-weight: 600;">No memories found</p>
        </div>
        '''

    stats = get_stats()

    # Type filter pills
    type_pills = ""
    type_all_class = "pill-active" if not type else "pill-inactive"
    type_pills += f'<a href="/memories?scope={scope}" class="pill {type_all_class}">All</a>'

    for t in sorted(stats["type_counts"].keys()):
        pill_class = "pill-active" if type == t else "pill-inactive"
        type_pills += f'<a href="/memories?type={t}&scope={scope}" class="pill {pill_class}">{t.title()}</a>'

    # Scope filter pills
    scope_all_class = "pill-active" if scope == "all" else "pill-inactive"
    scope_project_class = "pill-active" if scope == "project" else "pill-inactive"
    scope_global_class = "pill-active" if scope == "global" else "pill-inactive"

    content = f'''
    <div class="page-header">
        <div class="page-title">
            <span class="material-icons-round page-title-icon" style="color: #fbbf24;">inventory_2</span>
            <h1 class="page-title-text">Memories</h1>
        </div>
        <p class="page-subtitle">Explore and manage your persistent RAG knowledge base.</p>
    </div>

    <div style="padding: 0 3rem;">
        <div class="pills" style="margin-bottom: 1rem;">
            {type_pills}
        </div>

        <div class="pills" style="margin-bottom: 2rem;">
            <a href="/memories?type={type}&scope=all" class="pill {scope_all_class}">
                <span class="material-icons-round" style="font-size: 1rem;">language</span>
                All
            </a>
            <a href="/memories?type={type}&scope=project" class="pill {scope_project_class}">
                <span class="material-icons-round" style="font-size: 1rem;">folder</span>
                Project
            </a>
            <a href="/memories?type={type}&scope=global" class="pill {scope_global_class}">
                <span class="material-icons-round" style="font-size: 1rem;">public</span>
                Global
            </a>
        </div>

        <div id="memories-list" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 1.5rem; padding-bottom: 3rem;">
            {memories_html}
        </div>
    </div>
    '''

    return render_page(content, active="memories")


@app.get("/index", response_class=HTMLResponse)
async def index_page():
    """Index page"""
    content = '''
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 80vh; padding: 3rem;">
        <div style="width: 100%; max-width: 42rem;">
            <header style="margin-bottom: 2.5rem; text-align: center;">
                <div style="display: inline-flex; align-items: center; justify-content: center; padding: 0.75rem; margin-bottom: 1.5rem; border-radius: 1.5rem; background: rgba(251, 191, 36, 0.1); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.2);">
                    <span class="material-icons-round" style="font-size: 3rem;">folder</span>
                </div>
                <h2 style="font-size: 2.5rem; font-weight: 700; color: white; margin-bottom: 0.5rem;">Index Files</h2>
                <p style="color: #94a3b8; font-size: 1.125rem; font-weight: 500;">Add local resources to your semantic knowledge base</p>
            </header>

            <div class="glass-card" style="padding: 2rem; border-radius: 2rem;">
                <form hx-post="/api/index" hx-target="#index-result" hx-swap="innerHTML">
                    <div class="form-group">
                        <label class="form-label">Path to file or directory</label>
                        <div style="position: relative;">
                            <input type="text"
                                   name="path"
                                   class="form-input"
                                   placeholder="~/path/to/file_or_directory"
                                   style="font-family: 'Inter', monospace; padding-right: 3rem;">
                            <div style="position: absolute; inset: 0; left: auto; display: flex; align-items: center; padding-right: 1.25rem; pointer-events: none; color: #64748b;">
                                <span class="material-icons-round">terminal</span>
                            </div>
                        </div>
                    </div>

                    <div class="radio-group">
                        <label class="radio-label">
                            <input type="radio" name="scope" value="project" checked class="radio-input">
                            <span class="radio-text">
                                <span class="material-icons-round" style="font-size: 1.125rem;">folder_open</span>
                                Project
                            </span>
                        </label>
                        <label class="radio-label">
                            <input type="radio" name="scope" value="global" class="radio-input">
                            <span class="radio-text">
                                <span class="material-icons-round" style="font-size: 1.125rem;">public</span>
                                Global
                            </span>
                        </label>
                    </div>

                    <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; padding: 1rem 1.5rem;">
                        <span class="material-icons-round">upload_file</span>
                        <span>Index Content</span>
                    </button>

                    <div style="margin-top: 2rem; display: flex; align-items: start; gap: 1rem; padding: 1rem; border-radius: 0.75rem; background: rgba(99, 102, 241, 0.05); border: 1px solid rgba(99, 102, 241, 0.1);">
                        <span class="material-icons-round" style="color: var(--primary); font-size: 1.25rem; margin-top: 0.125rem;">info</span>
                        <p style="font-size: 0.875rem; color: #94a3b8; line-height: 1.6;">
                            Files will be processed using semantic chunking.
                            Supported formats: <code style="background: rgba(99, 102, 241, 0.2); color: var(--primary); padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-size: 0.75rem;">.md</code>,
                            <code style="background: rgba(99, 102, 241, 0.2); color: var(--primary); padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-size: 0.75rem;">.py</code>,
                            <code style="background: rgba(99, 102, 241, 0.2); color: var(--primary); padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-size: 0.75rem;">.txt</code>, and
                            <code style="background: rgba(99, 102, 241, 0.2); color: var(--primary); padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-size: 0.75rem;">.pdf</code>.
                        </p>
                    </div>
                </form>
                <div id="index-result" style="margin-top: 1.5rem;"></div>
            </div>

            <div style="margin-top: 3rem; display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">
                <div class="glass-card" style="padding: 1rem; text-align: center; border-radius: 1.5rem;">
                    <div style="color: var(--primary); margin-bottom: 0.5rem;">
                        <span class="material-icons-round">bolt</span>
                    </div>
                    <p style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: #64748b; letter-spacing: 0.05em;">Fast Indexing</p>
                </div>
                <div class="glass-card" style="padding: 1rem; text-align: center; border-radius: 1.5rem;">
                    <div style="color: var(--neon-cyan); margin-bottom: 0.5rem;">
                        <span class="material-icons-round">security</span>
                    </div>
                    <p style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: #64748b; letter-spacing: 0.05em;">Local Privacy</p>
                </div>
                <div class="glass-card" style="padding: 1rem; text-align: center; border-radius: 1.5rem;">
                    <div style="color: #fbbf24; margin-bottom: 0.5rem;">
                        <span class="material-icons-round">auto_awesome</span>
                    </div>
                    <p style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: #64748b; letter-spacing: 0.05em;">AI Ready</p>
                </div>
            </div>
        </div>
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
