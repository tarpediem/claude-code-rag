# Claude Code RAG - Roadmap

## Vision

Make claude-code-rag THE persistent memory solution for Claude Code: local-first, simple, and effective.

## 2026 Update: Production-Ready RAG

**Context**: Research shows 40-60% of RAG implementations fail in production due to:
- Poor observability (can't debug retrieval failures)
- Pure semantic search limitations (struggles with function names, paths)
- No reranking (low precision on complex queries)
- Context rot (memories drift, become stale)

**New focus**: Phases 9-11 address these pain points with features users actually need:
- **Hybrid search** (BM25 + semantic) for better precision
- **Reranking** with cross-encoders for query relevance
- **Observability** with query tracing and debug dashboards
- **Memory relations** for knowledge graphs
- **Session compression** with LLMs for token efficiency
- **Proactive context injection** to reduce round-trips

These features will make claude-code-rag production-grade, not just a prototype.

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

## Phase 7: UI & DX ✅

**Goal**: Easy to use and debug.

### Web UI ✅
- [x] Dashboard to view memories
- [x] Interactive search (HTMX live search)
- [x] Type/scope filtering
- [x] Visual stats with type breakdown
- [x] Memory browser with delete
- [x] File indexing form
- [x] Stack: FastAPI + HTMX (lightweight)
- [x] Modern dark theme
- [x] `claude-rag web`: Launch Web UI

### Enhanced TUI ✅
- [x] Memory view by type (sidebar tree)
- [x] Delete from TUI
- [x] Real-time search with debouncing
- [x] Command palette (Ctrl+P)
- [x] Modern styling (OpenCode-inspired)

### Enhanced CLI ✅
- [x] `claude-rag init`: Initial setup (check Ollama, pull model, create DB)
- [x] `claude-rag doctor`: Full diagnostics (Ollama, DB, MCP, Claude config)
- [x] `claude-rag serve`: Start MCP server
- [x] `claude-rag ui`: Launch TUI
- [x] `claude-rag web`: Launch Web UI
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

## Phase 9: Production-Ready RAG 🎯 (v0.10.0-0.11.0)

**Goal**: Address the 40-60% failure rate in production RAG systems with observability, hybrid search, and reranking.

### Observability & Debugging 🔄
- [ ] **Query tracing**: Log every retrieval with query → chunks → scores → used/not_used
- [ ] **Structured logging**: JSON logs for analysis
- [ ] **Debug dashboard**: Web UI panel showing last N queries with metrics
- [ ] **Latency breakdown**: Track embedding time, search time, rerank time separately
- [ ] **Quality feedback loop**: User can mark results as relevant/irrelevant

### Hybrid Search 🔄
- [ ] **BM25 integration**: Keyword search alongside semantic
- [ ] **Fusion strategy**: Combine BM25 + vector scores (RRF - Reciprocal Rank Fusion)
- [ ] **Query type detection**: Auto-detect if query needs keyword (function names, paths) vs semantic
- [ ] **Configurable weights**: Balance between keyword and semantic per query

### Reranking 🔄
- [ ] **Cross-encoder model**: `ms-marco-MiniLM-L-6-v2` for reranking
- [ ] **Two-stage retrieval**: Fast vector search (top 50) → precise reranking (top N)
- [ ] **Optional reranking**: `rerank=true` parameter in `rag_search`
- [ ] **Rerank cache**: Cache reranked results for identical queries

### Memory Relations 🔄
- [ ] **`relates_to` metadata**: Link memories together (bugfix → decision → architecture)
- [ ] **Relation types**: `causes`, `fixes`, `implements`, `deprecates`, `supersedes`
- [ ] **Graph traversal**: "Show me all decisions related to this bug"
- [ ] **Backlinks**: When viewing a memory, see what references it

---

## Phase 10: Advanced Intelligence 🧠 (v0.12.0-0.14.0)

**Goal**: Move from reactive retrieval to proactive, intelligent context management.

### Session Compression with LLM 🔄
- [ ] **LLM-based summarization**: Use Ollama to compress sessions before indexing
- [ ] **Extract essence**: Decisions, insights, patterns (not verbatim transcript)
- [ ] **Configurable compression**: `compress=true` in `rag_capture`
- [ ] **Token efficiency**: Store 70% less data with better semantic density

### Knowledge Graph 🔄
- [ ] **Graph database integration**: ChromaDB → Neo4j or LanceDB with relations
- [ ] **Visual graph explorer**: Web UI showing memory connections
- [ ] **Path queries**: "What decisions led to this architecture?"
- [ ] **Cluster detection**: Auto-group related memories

### Dual-Agent Architecture (GAM-inspired) 🔄
- [ ] **Memorizer agent**: Captures everything without filtering
- [ ] **Researcher agent**: Intelligent retrieval at query time
- [ ] **Separate collections**: `raw_memories` vs `curated_context`
- [ ] **Anti-context-rot**: Researcher validates and refreshes stale context

### Auto-Optimization 🔄
- [ ] **Dynamic chunk size**: Adjust based on file type and content complexity
- [ ] **Model switching**: Auto-select embedding model by language/domain
- [ ] **Learning from feedback**: Track which retrievals were useful, adjust strategy
- [ ] **A/B testing**: Compare chunk strategies, promote winner

### Proactive Context Injection 🔄
- [ ] **MCP hook**: Detect when Claude asks questions, auto-inject relevant context
- [ ] **Context suggestions**: "I found 3 related memories, add them?"
- [ ] **Pre-emptive search**: Analyze user message, search before Claude asks
- [ ] **Smart batching**: Reduce round-trips by including related context upfront

---

## Phase 11: Multi-Modal & Beyond 🌐 (v1.5.0+)

**Goal**: Support non-text data and advanced use cases.

### Multi-Modal Support 🔄
- [ ] **Diagram indexing**: Architecture diagrams → OCR + vision model embeddings
- [ ] **Screenshot search**: UI mockups → searchable with vision models
- [ ] **Video indexing**: Code review videos → transcription + key frame extraction
- [ ] **Audio notes**: Voice memos → transcribe + index

### Advanced Features 🔄
- [ ] **Multi-user**: Separate memories per user (team collaboration)
- [ ] **Encryption**: Encrypt local DB (LUKS or application-level)
- [ ] **Cloud sync**: Optional sync to self-hosted server
- [ ] **MCP Resources**: Expose memories as MCP resources (not just tools)
- [ ] **MCP Prompts**: Predefined prompts for common workflows
- [ ] **API server**: REST API for external integrations

---

## Backlog (Research/Experimental) 💭

- [ ] **Fine-tuned embeddings**: Train custom embedding model on user's codebase
- [ ] **Incremental learning**: Model adapts to user's terminology over time
- [ ] **Cross-project insights**: "This bug also happened in project X"
- [ ] **Time-travel**: "Show me the state of knowledge as of last week"
- [ ] **Conflict resolution**: Detect contradictory memories, suggest resolution

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
| 0.9.2 | Phase 7 - Web UI + TUI redesign ✅ |
| 0.9.3 | Bug fixes (ChromaDB 0.6.0, MCP boolean) ✅ |
| **0.10.0** | **Phase 9 - Hybrid search + BM25** |
| **0.10.5** | **Phase 9 - Reranking with cross-encoder** |
| **0.11.0** | **Phase 9 - Observability dashboard + tracing** |
| **0.11.5** | **Phase 9 - Memory relations + graph queries** |
| **0.12.0** | **Phase 10 - Session compression with LLM** |
| **0.13.0** | **Phase 10 - Knowledge graph + visualization** |
| **0.14.0** | **Phase 10 - Dual-agent architecture (GAM)** |
| **1.0.0** | **Stable, tested, documented, on PyPI** |
| **1.5.0** | **Phase 11 - Multi-modal support** |
| **2.0.0** | **Advanced features (encryption, cloud sync, API)** |

---

## Immediate priorities (2026 Q1-Q2)

### Done ✅
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

### Next (Production-Ready Features)
14. **Memory relations** — Add `relates_to` metadata (quick win, high value)
15. **Query tracing** — Structured logs for debugging retrievals
16. **Hybrid search (BM25 + semantic)** — Critical for function names, paths
17. **Reranking** — Cross-encoder for precision (v0.10.5)
18. **Debug dashboard** — Web UI panel for observability
19. **Session compression** — LLM-based summarization before indexing
20. **PyPI package** — Make it pip-installable (v1.0.0)

---

**v0.9.3 shipped! 🚀**

New in v0.9.3:
- Fix ChromaDB 0.6.0 compatibility (list_collections API change)
- Fix MCP Python boolean bug (false → False)
- All 13 MCP tools tested and validated
- Roadmap updated with production-ready features (Phases 9-11)

Previous versions:
- v0.9.2: Web UI dashboard (FastAPI + HTMX)
- v0.9.0: Enhanced CLI (init, doctor, serve, ui)
- v0.8.0: Performance (batch, cache, metrics)
- v0.7.0: Backup/Restore
- v0.6.0: Bidirectional sync

**Next milestone: v0.10.0** — Hybrid search (BM25 + semantic) + Memory relations
