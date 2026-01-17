#!/usr/bin/env python3
"""
Claude Code RAG - Terminal UI
Beautiful TUI for semantic search using Textual
"""
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Input, Button, Static, TabbedContent, TabPane, Log
from textual.binding import Binding
import subprocess
import os
import sys

# Find the claude_rag script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAG_SCRIPT = os.path.join(SCRIPT_DIR, "claude_rag.py")

# Fallback to system-installed version
if not os.path.exists(RAG_SCRIPT):
    RAG_SCRIPT = os.path.expanduser("~/.local/bin/claude-rag")


class ResultPanel(Static):
    """Panel pour afficher les résultats"""
    pass


class RagTUI(App):
    """Interface RAG Terminal"""

    CSS = """
    Screen {
        background: $surface;
    }

    #main {
        height: 100%;
        padding: 1;
    }

    Input {
        margin-bottom: 1;
    }

    Button {
        margin-right: 1;
    }

    .result-panel {
        height: 100%;
        border: solid $primary;
        padding: 1;
        overflow-y: auto;
    }

    .stats-panel {
        height: auto;
        border: solid $success;
        padding: 1;
        margin-bottom: 1;
    }

    #search-input {
        border: solid $primary;
    }

    #index-input {
        border: solid $warning;
    }

    .title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    Log {
        height: 100%;
        border: solid $secondary;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+s", "focus_search", "Search"),
        Binding("ctrl+i", "focus_index", "Index"),
        Binding("ctrl+r", "refresh_stats", "Stats"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with TabbedContent():
            with TabPane("Search", id="search-tab"):
                yield Static("Semantic Search", classes="title")
                yield Input(placeholder="Your question here...", id="search-input")
                yield Horizontal(
                    Button("Search", id="search-btn", variant="primary"),
                    Button("Clear", id="clear-btn", variant="default"),
                )
                yield ResultPanel("Results will appear here...", id="search-results", classes="result-panel")

            with TabPane("Index", id="index-tab"):
                yield Static("Index Documents", classes="title")
                yield Input(placeholder="~/path/to/file_or_directory", id="index-input")
                yield Button("Index", id="index-btn", variant="warning")
                yield ResultPanel("", id="index-results", classes="result-panel")

            with TabPane("Stats", id="stats-tab"):
                yield Static("RAG Statistics", classes="title")
                yield Button("Refresh", id="stats-btn", variant="success")
                yield ResultPanel("Loading...", id="stats-results", classes="stats-panel")
                yield Static("Recent Logs", classes="title")
                yield Log(id="log-panel")

        yield Footer()

    def on_mount(self) -> None:
        """On startup"""
        self.refresh_stats()
        self.query_one("#search-input").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "search-btn":
            self.do_search()
        elif event.button.id == "clear-btn":
            self.query_one("#search-input", Input).value = ""
            self.query_one("#search-results", ResultPanel).update("Results will appear here...")
        elif event.button.id == "index-btn":
            self.do_index()
        elif event.button.id == "stats-btn":
            self.refresh_stats()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in input"""
        if event.input.id == "search-input":
            self.do_search()
        elif event.input.id == "index-input":
            self.do_index()

    def do_search(self) -> None:
        """Execute search"""
        query = self.query_one("#search-input", Input).value
        if not query.strip():
            return

        result = subprocess.run(
            [sys.executable, RAG_SCRIPT, "search", query],
            capture_output=True, text=True
        )
        output = result.stdout or result.stderr or "No results"
        self.query_one("#search-results", ResultPanel).update(output)

        # Log
        log = self.query_one("#log-panel", Log)
        log.write_line(f"[search] {query[:50]}...")

    def do_index(self) -> None:
        """Execute indexing"""
        path = self.query_one("#index-input", Input).value
        if not path.strip():
            return

        path = os.path.expanduser(path)
        if not os.path.exists(path):
            self.query_one("#index-results", ResultPanel).update(f"Path not found: {path}")
            return

        result = subprocess.run(
            [sys.executable, RAG_SCRIPT, "index", path],
            capture_output=True, text=True
        )
        output = result.stdout or result.stderr or "Done"
        self.query_one("#index-results", ResultPanel).update(output)

        # Log and refresh stats
        log = self.query_one("#log-panel", Log)
        log.write_line(f"[index] {path}")
        self.refresh_stats()

    def refresh_stats(self) -> None:
        """Refresh stats"""
        result = subprocess.run(
            [sys.executable, RAG_SCRIPT, "stats"],
            capture_output=True, text=True
        )
        output = result.stdout or result.stderr or "Error"
        self.query_one("#stats-results", ResultPanel).update(output)

    def action_focus_search(self) -> None:
        """Focus on search"""
        self.query_one(TabbedContent).active = "search-tab"
        self.query_one("#search-input").focus()

    def action_focus_index(self) -> None:
        """Focus on indexing"""
        self.query_one(TabbedContent).active = "index-tab"
        self.query_one("#index-input").focus()

    def action_refresh_stats(self) -> None:
        """Refresh stats"""
        self.query_one(TabbedContent).active = "stats-tab"
        self.refresh_stats()


def main():
    app = RagTUI()
    app.title = "Claude Code RAG"
    app.run()


if __name__ == "__main__":
    main()
