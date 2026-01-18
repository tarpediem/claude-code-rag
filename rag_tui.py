#!/usr/bin/env python3
"""
Claude Code RAG - Modern Terminal UI
Inspired by OpenCode's clean TUI design
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    Markdown,
    ProgressBar,
    Rule,
    Sparkline,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    Tree,
)
from textual.widgets.tree import TreeNode

# Import RAG functions directly
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from claude_rag import (
        search_memories,
        index_path,
        get_stats,
        CHROMA_PATH,
    )
    DIRECT_IMPORT = True
except ImportError:
    DIRECT_IMPORT = False

# Try to import chromadb for direct access
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


def get_collection(scope: str = "project"):
    """Get ChromaDB collection"""
    if not CHROMA_AVAILABLE:
        return None
    project_path = os.getcwd()
    collection_name = f"claude_rag_{scope}_{hash(project_path) % 10**8}" if scope == "project" else f"claude_rag_{scope}"
    client = chromadb.PersistentClient(
        path=os.path.expanduser(CHROMA_PATH),
        settings=Settings(anonymized_telemetry=False)
    )
    try:
        return client.get_collection(collection_name)
    except Exception:
        return None


def format_timestamp(ts: str) -> str:
    """Format timestamp for display"""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts[:16] if len(ts) > 16 else ts


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM WIDGETS
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryCard(Static):
    """A card displaying a single memory"""

    DEFAULT_CSS = """
    MemoryCard {
        background: $surface;
        border: solid $primary-background;
        padding: 1;
        margin-bottom: 1;
        height: auto;
    }
    MemoryCard:hover {
        border: solid $primary;
    }
    MemoryCard .memory-type {
        color: $success;
        text-style: bold;
    }
    MemoryCard .memory-source {
        color: $text-muted;
        text-style: italic;
    }
    MemoryCard .memory-content {
        margin-top: 1;
    }
    MemoryCard .memory-score {
        color: $warning;
    }
    """

    def __init__(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        source: str,
        score: float = 0.0,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.memory_id = memory_id
        self.content = content
        self.memory_type = memory_type
        self.source = source
        self.score = score

    def compose(self) -> ComposeResult:
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
        icon = type_icons.get(self.memory_type, "💭")

        source_short = Path(self.source).name if self.source else "unknown"
        content_preview = self.content[:200] + "..." if len(self.content) > 200 else self.content

        yield Horizontal(
            Label(f"{icon} [{self.memory_type}]", classes="memory-type"),
            Label(f"  {source_short}", classes="memory-source"),
            Label(f"  Score: {self.score:.2f}", classes="memory-score") if self.score else Static(""),
        )
        yield Static(content_preview, classes="memory-content")


class StatsCard(Static):
    """A card for displaying statistics"""

    DEFAULT_CSS = """
    StatsCard {
        background: $surface;
        border: solid $primary-background;
        padding: 1;
        margin: 1;
        height: auto;
        min-width: 20;
    }
    StatsCard .stat-value {
        color: $primary;
        text-style: bold;
        text-align: center;
    }
    StatsCard .stat-label {
        color: $text-muted;
        text-align: center;
    }
    """

    def __init__(self, label: str, value: str, **kwargs):
        super().__init__(**kwargs)
        self.label = label
        self.value = value

    def compose(self) -> ComposeResult:
        yield Static(self.value, classes="stat-value")
        yield Static(self.label, classes="stat-label")


class CommandPalette(ModalScreen):
    """Command palette for quick actions"""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    CommandPalette {
        align: center middle;
    }
    CommandPalette > Container {
        width: 60;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    CommandPalette Input {
        margin-bottom: 1;
    }
    CommandPalette ListView {
        height: auto;
        max-height: 20;
    }
    CommandPalette ListItem {
        padding: 0 1;
    }
    CommandPalette ListItem:hover {
        background: $primary-background;
    }
    """

    COMMANDS = [
        ("search", "🔍 Search memories", "s"),
        ("index", "📁 Index file/directory", "i"),
        ("stats", "📊 View statistics", "t"),
        ("memories", "📚 Browse memories", "m"),
        ("delete", "🗑️ Delete memory", "d"),
        ("refresh", "🔄 Refresh all", "r"),
        ("quit", "👋 Quit", "q"),
    ]

    def compose(self) -> ComposeResult:
        with Container():
            yield Input(placeholder="Type a command...", id="cmd-input")
            yield ListView(
                *[ListItem(Label(f"{cmd[1]} ({cmd[2]})"), id=cmd[0]) for cmd in self.COMMANDS],
                id="cmd-list"
            )

    def on_mount(self) -> None:
        self.query_one("#cmd-input").focus()

    @on(Input.Changed, "#cmd-input")
    def filter_commands(self, event: Input.Changed) -> None:
        query = event.value.lower()
        list_view = self.query_one("#cmd-list", ListView)
        for item in list_view.query(ListItem):
            cmd_name = item.id or ""
            visible = query in cmd_name or not query
            item.display = visible

    @on(ListView.Selected)
    def on_command_selected(self, event: ListView.Selected) -> None:
        if event.item.id:
            self.dismiss(event.item.id)

    @on(Input.Submitted, "#cmd-input")
    def on_submit(self, event: Input.Submitted) -> None:
        # Execute first visible command
        list_view = self.query_one("#cmd-list", ListView)
        for item in list_view.query(ListItem):
            if item.display and item.id:
                self.dismiss(item.id)
                return


class DeleteConfirmScreen(ModalScreen[bool]):
    """Confirmation screen for deletion"""

    DEFAULT_CSS = """
    DeleteConfirmScreen {
        align: center middle;
    }
    DeleteConfirmScreen > Container {
        width: 50;
        height: auto;
        background: $surface;
        border: thick $error;
        padding: 2;
    }
    DeleteConfirmScreen .title {
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }
    DeleteConfirmScreen .buttons {
        margin-top: 2;
        align: center middle;
    }
    DeleteConfirmScreen Button {
        margin: 0 1;
    }
    """

    def __init__(self, memory_id: str, content_preview: str, **kwargs):
        super().__init__(**kwargs)
        self.memory_id = memory_id
        self.content_preview = content_preview

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("🗑️ Delete Memory?", classes="title")
            yield Static(f"ID: {self.memory_id}")
            yield Static(f"Content: {self.content_preview[:100]}...")
            yield Rule()
            with Horizontal(classes="buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Delete", variant="error", id="delete")

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#delete")
    def on_delete(self) -> None:
        self.dismiss(True)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

class RagTUI(App):
    """Claude Code RAG - Modern Terminal UI"""

    TITLE = "Claude Code RAG"
    SUB_TITLE = "Semantic Memory for Claude Code"

    CSS = """
    /* ════════════════════════════════════════════════════════════════════════
       GLOBAL STYLES
       ════════════════════════════════════════════════════════════════════════ */

    Screen {
        background: $background;
    }

    /* ════════════════════════════════════════════════════════════════════════
       SIDEBAR
       ════════════════════════════════════════════════════════════════════════ */

    #sidebar {
        width: 28;
        background: $surface;
        border-right: solid $primary-background;
        padding: 1;
    }

    #sidebar .sidebar-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        text-align: center;
    }

    #sidebar .scope-selector {
        margin-bottom: 1;
        height: auto;
    }

    #sidebar .scope-label {
        margin-right: 1;
    }

    #type-tree {
        height: 1fr;
        scrollbar-gutter: stable;
    }

    #type-tree > .tree--guides {
        color: $primary-background;
    }

    /* ════════════════════════════════════════════════════════════════════════
       MAIN CONTENT
       ════════════════════════════════════════════════════════════════════════ */

    #main-content {
        width: 1fr;
    }

    #search-bar {
        height: 3;
        padding: 0 1;
        background: $surface;
        border-bottom: solid $primary-background;
    }

    #search-input {
        width: 1fr;
        border: none;
        background: transparent;
    }

    #search-input:focus {
        border: none;
    }

    #results-area {
        height: 1fr;
        padding: 1;
    }

    #results-scroll {
        height: 1fr;
    }

    #status-bar {
        height: 1;
        background: $surface;
        border-top: solid $primary-background;
        padding: 0 1;
        color: $text-muted;
    }

    /* ════════════════════════════════════════════════════════════════════════
       STATS TAB
       ════════════════════════════════════════════════════════════════════════ */

    #stats-container {
        padding: 2;
    }

    #stats-cards {
        height: auto;
        align: center top;
    }

    #stats-details {
        margin-top: 2;
        height: auto;
    }

    #type-breakdown {
        width: 1fr;
        height: auto;
        background: $surface;
        border: solid $primary-background;
        padding: 1;
        margin: 1;
    }

    .type-row {
        height: auto;
    }

    .type-name {
        width: 15;
    }

    .type-bar {
        width: 1fr;
        margin: 0 1;
    }

    .type-count {
        width: 8;
        text-align: right;
    }

    /* ════════════════════════════════════════════════════════════════════════
       INDEX TAB
       ════════════════════════════════════════════════════════════════════════ */

    #index-container {
        padding: 2;
    }

    #path-input {
        margin-bottom: 1;
    }

    #index-options {
        height: auto;
        margin-bottom: 1;
    }

    #index-log {
        height: 1fr;
        background: $surface;
        border: solid $primary-background;
        padding: 1;
    }

    /* ════════════════════════════════════════════════════════════════════════
       MEMORY DETAIL VIEW
       ════════════════════════════════════════════════════════════════════════ */

    #detail-view {
        display: none;
        width: 40%;
        background: $surface;
        border-left: solid $primary;
        padding: 1;
    }

    #detail-view.visible {
        display: block;
    }

    #detail-header {
        height: auto;
        margin-bottom: 1;
    }

    #detail-content {
        height: 1fr;
        overflow-y: auto;
    }

    #detail-actions {
        height: auto;
        margin-top: 1;
    }

    /* ════════════════════════════════════════════════════════════════════════
       LOADING
       ════════════════════════════════════════════════════════════════════════ */

    LoadingIndicator {
        background: transparent;
    }

    .hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("ctrl+p", "command_palette", "Commands", show=True),
        Binding("/", "focus_search", "Search", show=True),
        Binding("escape", "clear_selection", "Clear", show=False),
        Binding("ctrl+r", "refresh", "Refresh", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("1", "tab_search", "Search", show=False),
        Binding("2", "tab_stats", "Stats", show=False),
        Binding("3", "tab_index", "Index", show=False),
        Binding("d", "delete_selected", "Delete", show=False),
    ]

    # Reactive state
    current_scope = reactive("all")
    selected_type = reactive("")
    selected_memory_id = reactive("")
    search_query = reactive("")
    is_loading = reactive(False)

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal():
            # Sidebar
            with Vertical(id="sidebar"):
                yield Static("📚 Memory Browser", classes="sidebar-title")

                with Horizontal(classes="scope-selector"):
                    yield Label("Scope:", classes="scope-label")
                    yield Button("All", id="scope-all", variant="primary")
                    yield Button("📁", id="scope-project", variant="default")
                    yield Button("🌐", id="scope-global", variant="default")

                yield Tree("Memory Types", id="type-tree")

            # Main content area
            with Vertical(id="main-content"):
                with TabbedContent():
                    with TabPane("🔍 Search", id="tab-search"):
                        with Horizontal(id="search-bar"):
                            yield Input(
                                placeholder="Search memories... (press / to focus)",
                                id="search-input"
                            )

                        with Horizontal():
                            with ScrollableContainer(id="results-scroll"):
                                yield Vertical(id="results-area")

                            yield Vertical(id="detail-view")

                        yield Static("Ready", id="status-bar")

                    with TabPane("📊 Stats", id="tab-stats"):
                        with Vertical(id="stats-container"):
                            yield Horizontal(id="stats-cards")
                            yield Vertical(id="stats-details")

                    with TabPane("📁 Index", id="tab-index"):
                        with Vertical(id="index-container"):
                            yield Static("Index files or directories into memory")
                            yield Input(
                                placeholder="~/path/to/file_or_directory",
                                id="path-input"
                            )
                            with Horizontal(id="index-options"):
                                yield Label("Scope: ")
                                yield Button("📁 Project", id="idx-project", variant="primary")
                                yield Button("🌐 Global", id="idx-global", variant="default")
                                yield Button("Index", id="idx-btn", variant="success")

                            yield Static("", id="index-log")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app"""
        self.refresh_type_tree()
        self.refresh_stats()
        self.query_one("#search-input").focus()

    # ─────────────────────────────────────────────────────────────────────────
    # SEARCH FUNCTIONALITY
    # ─────────────────────────────────────────────────────────────────────────

    @on(Input.Submitted, "#search-input")
    def on_search_submit(self, event: Input.Submitted) -> None:
        """Handle search submission"""
        self.search_query = event.value
        self.do_search(event.value)

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Live search as you type (debounced)"""
        if len(event.value) >= 3:
            self.search_query = event.value
            self.do_search_debounced(event.value)

    @work(exclusive=True, group="search")
    async def do_search_debounced(self, query: str) -> None:
        """Debounced search"""
        import asyncio
        await asyncio.sleep(0.3)  # 300ms debounce
        if query == self.search_query:  # Still the same query
            self.do_search(query)

    def do_search(self, query: str) -> None:
        """Execute search"""
        if not query.strip():
            return

        self.is_loading = True
        self.update_status(f"Searching for: {query}")

        results_area = self.query_one("#results-area")
        results_area.remove_children()

        try:
            # Get scope
            scope = None if self.current_scope == "all" else self.current_scope

            # Search
            if DIRECT_IMPORT:
                results = search_memories(query, n_results=20, scope=scope)
            else:
                results = self._search_via_cli(query)

            if not results:
                results_area.mount(Static("No results found."))
            else:
                for r in results:
                    card = MemoryCard(
                        memory_id=r.get("id", ""),
                        content=r.get("content", ""),
                        memory_type=r.get("type", "context"),
                        source=r.get("source", ""),
                        score=r.get("score", 0.0),
                    )
                    results_area.mount(card)

            self.update_status(f"Found {len(results)} results for: {query}")

        except Exception as e:
            results_area.mount(Static(f"Error: {e}"))
            self.update_status(f"Search error: {e}")

        self.is_loading = False

    def _search_via_cli(self, query: str) -> list:
        """Fallback search via CLI"""
        import subprocess
        import json

        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "claude_rag.py"), "search", query, "--json"],
            capture_output=True, text=True
        )
        try:
            return json.loads(result.stdout)
        except Exception:
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # TYPE TREE
    # ─────────────────────────────────────────────────────────────────────────

    def refresh_type_tree(self) -> None:
        """Refresh the memory type tree"""
        tree = self.query_one("#type-tree", Tree)
        tree.clear()

        type_counts = self._get_type_counts()
        total = sum(type_counts.values())

        # Add "All" node
        tree.root.add_leaf(f"📋 All ({total})", data={"type": ""})

        # Add type nodes
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

        for mem_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            icon = type_icons.get(mem_type, "💭")
            tree.root.add_leaf(f"{icon} {mem_type} ({count})", data={"type": mem_type})

        tree.root.expand()

    def _get_type_counts(self) -> dict:
        """Get counts by memory type"""
        counts = {}

        for scope in ["project", "global"]:
            if self.current_scope != "all" and self.current_scope != scope:
                continue

            collection = get_collection(scope)
            if not collection:
                continue

            try:
                all_data = collection.get(include=["metadatas"])
                for meta in all_data.get("metadatas", []):
                    mem_type = meta.get("memory_type") or meta.get("type", "context")
                    counts[mem_type] = counts.get(mem_type, 0) + 1
            except Exception:
                pass

        return counts

    @on(Tree.NodeSelected, "#type-tree")
    def on_type_selected(self, event: Tree.NodeSelected) -> None:
        """Handle type selection in tree"""
        if event.node.data:
            self.selected_type = event.node.data.get("type", "")
            self.filter_by_type(self.selected_type)

    def filter_by_type(self, memory_type: str) -> None:
        """Filter results by type"""
        self.update_status(f"Filtering by type: {memory_type or 'All'}")
        # Re-run search with type filter if there's a query
        if self.search_query:
            self.do_search(self.search_query)

    # ─────────────────────────────────────────────────────────────────────────
    # STATS
    # ─────────────────────────────────────────────────────────────────────────

    def refresh_stats(self) -> None:
        """Refresh statistics display"""
        cards_container = self.query_one("#stats-cards")
        details_container = self.query_one("#stats-details")

        cards_container.remove_children()
        details_container.remove_children()

        # Get stats
        project_count = 0
        global_count = 0
        type_counts = {}

        for scope in ["project", "global"]:
            collection = get_collection(scope)
            if collection:
                try:
                    count = collection.count()
                    if scope == "project":
                        project_count = count
                    else:
                        global_count = count

                    # Get type breakdown
                    all_data = collection.get(include=["metadatas"])
                    for meta in all_data.get("metadatas", []):
                        mem_type = meta.get("memory_type") or meta.get("type", "context")
                        type_counts[mem_type] = type_counts.get(mem_type, 0) + 1
                except Exception:
                    pass

        total = project_count + global_count

        # Add stat cards
        cards_container.mount(StatsCard("Total Memories", str(total)))
        cards_container.mount(StatsCard("📁 Project", str(project_count)))
        cards_container.mount(StatsCard("🌐 Global", str(global_count)))
        cards_container.mount(StatsCard("Types", str(len(type_counts))))

        # Add type breakdown
        if type_counts:
            details_container.mount(Static("Memory Types Breakdown:", classes="sidebar-title"))

            max_count = max(type_counts.values()) if type_counts else 1

            for mem_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
                pct = int((count / max_count) * 20)
                bar = "█" * pct + "░" * (20 - pct)

                with Horizontal(classes="type-row"):
                    details_container.mount(
                        Horizontal(
                            Static(mem_type, classes="type-name"),
                            Static(bar, classes="type-bar"),
                            Static(str(count), classes="type-count"),
                            classes="type-row"
                        )
                    )

    # ─────────────────────────────────────────────────────────────────────────
    # INDEXING
    # ─────────────────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#idx-btn")
    def on_index_click(self) -> None:
        """Handle index button click"""
        path = self.query_one("#path-input", Input).value
        self.do_index(path)

    @on(Input.Submitted, "#path-input")
    def on_path_submit(self, event: Input.Submitted) -> None:
        """Handle path input submission"""
        self.do_index(event.value)

    @on(Button.Pressed, "#idx-project")
    def on_idx_project(self) -> None:
        self.query_one("#idx-project").variant = "primary"
        self.query_one("#idx-global").variant = "default"

    @on(Button.Pressed, "#idx-global")
    def on_idx_global(self) -> None:
        self.query_one("#idx-global").variant = "primary"
        self.query_one("#idx-project").variant = "default"

    def do_index(self, path: str) -> None:
        """Execute indexing"""
        if not path.strip():
            return

        path = os.path.expanduser(path)
        log = self.query_one("#index-log", Static)

        if not os.path.exists(path):
            log.update(f"❌ Path not found: {path}")
            return

        log.update(f"⏳ Indexing: {path}...")

        try:
            scope = "global" if self.query_one("#idx-global").variant == "primary" else "project"

            if DIRECT_IMPORT:
                result = index_path(path, scope=scope)
                log.update(f"✅ Indexed: {result}")
            else:
                import subprocess
                result = subprocess.run(
                    [sys.executable, str(SCRIPT_DIR / "claude_rag.py"), "index", path, "--scope", scope],
                    capture_output=True, text=True
                )
                log.update(result.stdout or result.stderr or "✅ Done")

            # Refresh type tree and stats
            self.refresh_type_tree()
            self.refresh_stats()

        except Exception as e:
            log.update(f"❌ Error: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # SCOPE SWITCHING
    # ─────────────────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#scope-all")
    def on_scope_all(self) -> None:
        self._set_scope("all")

    @on(Button.Pressed, "#scope-project")
    def on_scope_project(self) -> None:
        self._set_scope("project")

    @on(Button.Pressed, "#scope-global")
    def on_scope_global(self) -> None:
        self._set_scope("global")

    def _set_scope(self, scope: str) -> None:
        """Set the current scope"""
        self.current_scope = scope

        # Update button variants
        self.query_one("#scope-all").variant = "primary" if scope == "all" else "default"
        self.query_one("#scope-project").variant = "primary" if scope == "project" else "default"
        self.query_one("#scope-global").variant = "primary" if scope == "global" else "default"

        # Refresh
        self.refresh_type_tree()
        if self.search_query:
            self.do_search(self.search_query)

    # ─────────────────────────────────────────────────────────────────────────
    # ACTIONS
    # ─────────────────────────────────────────────────────────────────────────

    def action_command_palette(self) -> None:
        """Show command palette"""
        def handle_command(cmd: str | None) -> None:
            if cmd == "search":
                self.action_focus_search()
            elif cmd == "stats":
                self.action_tab_stats()
            elif cmd == "index":
                self.action_tab_index()
            elif cmd == "refresh":
                self.action_refresh()
            elif cmd == "quit":
                self.action_quit()

        self.push_screen(CommandPalette(), handle_command)

    def action_focus_search(self) -> None:
        """Focus search input"""
        self.query_one(TabbedContent).active = "tab-search"
        self.query_one("#search-input").focus()

    def action_clear_selection(self) -> None:
        """Clear selection and close detail view"""
        self.selected_memory_id = ""
        detail_view = self.query_one("#detail-view")
        detail_view.remove_class("visible")

    def action_refresh(self) -> None:
        """Refresh everything"""
        self.refresh_type_tree()
        self.refresh_stats()
        if self.search_query:
            self.do_search(self.search_query)
        self.update_status("Refreshed")

    def action_tab_search(self) -> None:
        self.query_one(TabbedContent).active = "tab-search"

    def action_tab_stats(self) -> None:
        self.query_one(TabbedContent).active = "tab-stats"
        self.refresh_stats()

    def action_tab_index(self) -> None:
        self.query_one(TabbedContent).active = "tab-index"

    def action_delete_selected(self) -> None:
        """Delete selected memory"""
        # TODO: Implement with selected memory from results
        pass

    def update_status(self, message: str) -> None:
        """Update status bar"""
        status = self.query_one("#status-bar", Static)
        status.update(f"  {message}")


def main():
    app = RagTUI()
    app.run()


if __name__ == "__main__":
    main()
