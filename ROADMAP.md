# Claude Code RAG - Roadmap

## Vision

Make claude-code-rag THE persistent memory solution for Claude Code: local-first, simple, and effective.

---

## Phase 1: Stabilization & Polish ✅

**Goal**: An MCP server that works perfectly out of the box.

### Done ✅
- [x] Basic MCP server with 5 tools
- [x] Ollama + ChromaDB integration
- [x] Standalone CLI (`claude_rag.py`)
- [x] TUI with Textual (`rag_tui.py`)
- [x] **Tests**: Unit tests for chunking
- [x] **Health check**: `rag_health` tool to verify Ollama/ChromaDB
- [x] **requirements.txt**: Complete with mcp

### To do (optional)
- [ ] **Error handling**: Better error messages
- [ ] **Logging**: Debug option for troubleshooting

---

## Phase 2: Enhanced Indexing ✅

**Goal**: Index more than markdown, intelligently.

### Multi-format support ✅
- [x] `.txt` — Plain text
- [x] `.py` — Python code (split by def/class)
- [x] `.js` / `.ts` — JavaScript/TypeScript (split by function/const/export)
- [x] `.json` — JSON configs
- [x] `.yaml` / `.yml` — YAML configs
- [x] `.sh` / `.fish` — Shell scripts
- [x] `.toml` — TOML configs

### Intelligent chunking ✅
- [x] **Markdown**: Split by headers (`## Section`)
- [x] **Python code**: Split by functions/classes
- [x] **JS/TS code**: Split by functions
- [x] **Configs**: Generic chunking with overlap

### Enriched metadata
- [x] `file_type`: File extension
- [x] `source`: Full path
- [ ] `indexed_at`: Indexing timestamp
- [ ] `file_hash`: Hash to detect changes
- [ ] `chunk_index`: Position in file

---

## Phase 3: Memory Types & Organization 🔄

**Goal**: Not just "text", but structured memory types.

### Memory types ✅
- [x] `context` — General context (indexed files)
- [x] `decision` — Technical decisions made
- [x] `bugfix` — Bugs resolved and solutions
- [x] `architecture` — Architecture choices
- [x] `preference` — User preferences
- [x] `snippet` — Reusable code snippets

### Tool `rag_store` ✅
```python
rag_store(
    content: str,       # Content to store
    memory_type: str,   # Memory type
    tags: list[str]     # Optional tags
)
```

### Tool `rag_forget` 🔄
```python
rag_forget(
    query: str,         # Search for memories to delete
    confirm: bool       # Confirmation required
)
```

### Tool `rag_list` 🔄
```python
rag_list(
    memory_type: str,   # Filter by type (optional)
    limit: int          # Max results
)
```

### Type filtering in search ✅
- [x] Add `memory_type` filter in `rag_search`

---

## Phase 4: Auto-capture ✅

**Goal**: Automatically capture context from Claude Code sessions.

### Session Parser ✅
- [x] Parse `.jsonl` files in `~/.claude/projects/`
- [x] Extract important decisions
- [x] Auto-index with `rag_capture` tool
- [ ] Summarize sessions with local LLM (optional)

### Pattern detection ✅
- [x] Detect key phrases: "I decided", "we'll use", "the fix is"
- [x] Automatically tag memory type (decision, bugfix, architecture, etc.)
- [x] Confidence scoring (0-1)

### Tool `rag_capture` ✅
```python
rag_capture(
    max_sessions: int,      # Number of sessions to parse (default: 3)
    min_confidence: float,  # Confidence threshold (default: 0.7)
    dry_run: bool           # Preview without storing (default: false)
)
```

### Config (future)
```bash
# ~/.claude-rag/config.yaml
auto_capture:
  enabled: true
  session_summary: true
  watch_paths:
    - ~/projects/*/CLAUDE.md
```

---

## Phase 5: Export & Sync 🔄

**Goal**: Memory must be exportable from RAG.

### Multi-format export ✅
- [x] Tool `rag_export`: Export to AGENTS.md, CLAUDE.md, GEMINI.md, etc.
- [x] Support 5 formats: agents, claude, gemini, aider, cursor
- [x] Filtering by memory_type and scope
- [x] Symlink creation for cross-agent compatibility
- [x] Markdown format organized by sections (Decisions, Architecture, Bugfixes...)

### Bidirectional sync ✅
- [x] Tool `rag_sync`: On-demand sync with change detection (SHA256 hash)
- [x] Hash-based IDs for auto-dedup (ChromaDB upsert)
- [x] `sync_state.json`: Track indexed files and their hashes
- [x] Anti-loop protection: Refuse to export to source files

### Backup & Restore ✅
- [x] `rag_backup`: Complete JSON export (documents, metadatas, embeddings)
- [x] `rag_restore`: Import with merge or replace mode
- [x] Multi-scope support (project, global, all)
- [x] Embeddings saved for fast restore without recalculation

---

## Phase 6: Multi-model & Performance 🚀

**Goal**: Faster, more flexible.

### Multi-model support
- [ ] `nomic-embed-text` (default, 274MB)
- [ ] `nomic-embed-text-v2-moe` (multilingual, 958MB)
- [ ] `mxbai-embed-large` (high quality, 670MB)
- [ ] `all-minilm` (tiny & fast, 46MB)

### Optimizations ✅
- [x] Batch embeddings (`get_embeddings_batch()` - one API call for N chunks)
- [x] Embedding cache (in-memory, hash-based)
- [x] Incremental index (`rag_sync` with SHA256 hash)
- [ ] Async for large indexing (optional)

### Metrics ✅
- [x] DB size on disk
- [x] Cache hit rate
- [x] Stats in `rag_stats` (hits, misses, cache size)

---

## Phase 7: UI & DX 🎨

**Goal**: Easy to use and debug.

### Web UI (optional)
- [ ] Dashboard to view memories
- [ ] Interactive search
- [ ] Type/tag management
- [ ] Visual stats
- [ ] Stack: FastAPI + HTMX (lightweight)

### Enhanced TUI
- [ ] Memory view by type
- [ ] Delete/edit from TUI
- [ ] Real-time search

### Enhanced CLI ✅
- [x] `claude-rag init`: Initial setup (check Ollama, pull model, create DB)
- [x] `claude-rag doctor`: Full diagnostics (Ollama, DB, MCP, Claude config)
- [x] `claude-rag serve`: Start MCP server
- [x] `claude-rag ui`: Launch TUI
- [x] argparse with proper subcommands

---

## Phase 8: Community & Distribution 📦

**Goal**: Easy to install, easy to contribute.

### Packaging
- [ ] Publish on PyPI: `pip install claude-code-rag`
- [ ] Entry point: `claude-rag` available directly
- [ ] MCP installable via: `claude mcp add rag -- pip run claude-code-rag`

### Documentation
- [ ] Complete README with GIFs
- [ ] CONTRIBUTING.md
- [ ] Advanced usage examples
- [ ] Troubleshooting guide

### Promotion
- [ ] Post Reddit r/ClaudeAI
- [ ] Post Reddit r/LocalLLaMA
- [ ] Post Reddit r/selfhosted
- [ ] Medium/Dev.to article
- [ ] Demo video (30s GIF or YouTube)

---

## Nice to Have (Backlog) 💭

- [ ] **Hybrid search**: Keyword + semantic combined
- [ ] **Reranking**: Rerank results with dedicated model
- [ ] **Knowledge graph**: Relations between memories
- [ ] **Multi-user**: Separate memories per user
- [ ] **Encryption**: Encrypt local DB
- [ ] **Cloud sync**: Optional sync to server (self-hosted)
- [ ] **MCP Resources**: Expose memories as MCP resources
- [ ] **MCP Prompts**: Predefined prompts for common workflows

---

## Versioning

| Version | Milestone |
|---------|-----------|
| 0.1.0 | Basic MCP server |
| 0.2.0 | Phase 2 - Multi-formats + intelligent chunking |
| 0.3.0 | Phase 3 - Memory types |
| 0.4.0 | Phase 4 - Auto-capture |
| 0.4.1 | Dual-scope memory (project + global) |
| 0.5.0 | Phase 5 - Multi-format export (AGENTS.md, CLAUDE.md, etc.) ✅ |
| 0.6.0 | Phase 5 - Bidirectional sync (`rag_sync` + anti-loop protection) ✅ |
| 0.7.0 | Phase 5 - Backup/Restore (`rag_backup`, `rag_restore`) ✅ |
| 0.8.0 | Phase 6 - Performance (batch embeddings, cache, metrics) ✅ |
| 0.9.0 | Phase 7 - Enhanced CLI (init, doctor, serve, ui) ✅ |
| 1.0.0 | Stable, tested, documented, on PyPI |

---

## Immediate priorities

1. ~~**Basic tests**~~ ✅
2. ~~**Multi-formats**~~ ✅
3. ~~**Markdown chunking**~~ ✅
4. ~~**`rag_store` tool**~~ ✅
5. ~~**README with GIF**~~ ✅
6. ~~**`rag_forget` tool**~~ ✅
7. ~~**Dual-scope memory**~~ ✅ (project + global)
8. ~~**`rag_list` tool**~~ ✅
9. ~~**Search filtering**~~ ✅
10. ~~**`rag_capture` tool**~~ ✅ — Auto-capture sessions
11. ~~**`rag_export` tool**~~ ✅ — Multi-format export (AGENTS.md, CLAUDE.md, GEMINI.md...)
12. ~~**Bidirectional sync**~~ ✅ — `rag_sync` + anti-loop protection
13. ~~**Backup & Restore**~~ ✅ — `rag_backup` + `rag_restore`
14. **PyPI package** — Phase 8

---

**v0.9.0 shipped! 🚀**

New in v0.9.0:
- `claude-rag init` - Setup wizard
- `claude-rag doctor` - Full diagnostics
- `claude-rag serve` - Start MCP server
- argparse-based CLI with subcommands

Previous versions:
- v0.8.0: Performance (batch, cache, metrics)
- v0.7.0: Backup/Restore
- v0.6.0: Bidirectional sync
