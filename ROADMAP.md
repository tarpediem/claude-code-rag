# Claude Code RAG - Roadmap

## Vision

Faire de claude-code-rag LA solution de mémoire persistante pour Claude Code : local-first, simple, et efficace.

---

## Phase 1 : Stabilisation & Polish ✅

**Objectif** : Un MCP server qui marche nickel out of the box.

### Done ✅
- [x] MCP server basique avec 5 tools
- [x] Intégration Ollama + ChromaDB
- [x] CLI standalone (`claude_rag.py`)
- [x] TUI avec Textual (`rag_tui.py`)
- [x] **Tests** : Tests unitaires pour le chunking
- [x] **Health check** : Tool `rag_health` pour vérifier Ollama/ChromaDB
- [x] **requirements.txt** : Complet avec mcp

### À faire (optionnel)
- [ ] **Error handling** : Meilleurs messages d'erreur
- [ ] **Logging** : Option debug pour troubleshoot

---

## Phase 2 : Indexation Améliorée ✅

**Objectif** : Indexer plus que du markdown, de manière intelligente.

### Support multi-formats ✅
- [x] `.txt` — Texte brut
- [x] `.py` — Code Python (split par def/class)
- [x] `.js` / `.ts` — JavaScript/TypeScript (split par function/const/export)
- [x] `.json` — Configs JSON
- [x] `.yaml` / `.yml` — Configs YAML
- [x] `.sh` / `.fish` — Scripts shell
- [x] `.toml` — Configs TOML

### Chunking intelligent ✅
- [x] **Markdown** : Split par headers (`## Section`)
- [x] **Code Python** : Split par fonctions/classes
- [x] **Code JS/TS** : Split par fonctions
- [x] **Configs** : Chunking générique avec overlap

### Métadonnées enrichies
- [x] `file_type` : Extension du fichier
- [x] `source` : Chemin complet
- [ ] `indexed_at` : Timestamp d'indexation
- [ ] `file_hash` : Hash pour détecter les changements
- [ ] `chunk_index` : Position dans le fichier

---

## Phase 3 : Memory Types & Organisation 🔄

**Objectif** : Pas juste "du texte", mais des types de mémoire structurés.

### Types de mémoire ✅
- [x] `context` — Contexte général (fichiers indexés)
- [x] `decision` — Décisions techniques prises
- [x] `bugfix` — Bugs résolus et solutions
- [x] `architecture` — Choix d'architecture
- [x] `preference` — Préférences utilisateur
- [x] `snippet` — Bouts de code réutilisables

### Tool `rag_store` ✅
```python
rag_store(
    content: str,       # Le contenu à stocker
    memory_type: str,   # Type de mémoire
    tags: list[str]     # Tags optionnels
)
```

### Tool `rag_forget` 🔄
```python
rag_forget(
    query: str,         # Recherche les memories à supprimer
    confirm: bool       # Confirmation requise
)
```

### Tool `rag_list` 🔄
```python
rag_list(
    memory_type: str,   # Filtrer par type (optionnel)
    limit: int          # Nombre max de résultats
)
```

### Filtrage par type dans search ✅
- [x] Ajouter `memory_type` en filtre dans `rag_search`

---

## Phase 4 : Auto-capture ✅

**Objectif** : Capturer automatiquement le contexte des sessions Claude Code.

### Session Parser ✅
- [x] Parser les fichiers `.jsonl` dans `~/.claude/projects/`
- [x] Extraire les décisions importantes
- [x] Auto-index avec `rag_capture` tool
- [ ] Résumer les sessions avec un LLM local (optionnel)

### Détection de patterns ✅
- [x] Détecter les phrases clés : "j'ai décidé", "on va utiliser", "le fix c'est"
- [x] Marquer automatiquement le type de mémoire (decision, bugfix, architecture, etc.)
- [x] Scoring de confiance (0-1)

### Tool `rag_capture` ✅
```python
rag_capture(
    max_sessions: int,      # Nombre de sessions à parser (défaut: 3)
    min_confidence: float,  # Seuil de confiance (défaut: 0.7)
    dry_run: bool           # Preview sans stocker (défaut: false)
)
```

### Config (future)
```bash
# ~/.claude-rag/config.yaml
auto_capture:
  enabled: true
  session_summary: true
  watch_paths:
    - ~/projets/*/CLAUDE.md
```

---

## Phase 5 : Export & Sync 🔄

**Objectif** : La mémoire doit pouvoir sortir du RAG.

### Export multi-format ✅
- [x] Tool `rag_export` : Export vers AGENTS.md, CLAUDE.md, GEMINI.md, etc.
- [x] Support 5 formats : agents, claude, gemini, aider, cursor
- [x] Filtrage par memory_type et scope
- [x] Création de symlinks pour compatibilité cross-agent
- [x] Format markdown organisé par sections (Decisions, Architecture, Bugfixes...)

### Sync bidirectionnelle ✅
- [x] Tool `rag_sync` : Sync on-demand avec détection de changements (hash SHA256)
- [x] Hash-based IDs pour auto-dedup (ChromaDB upsert)
- [x] `sync_state.json` : Track les fichiers indexés et leurs hash
- [x] Protection anti-boucle : Refuse d'exporter vers fichiers sources

### Backup & Restore ✅
- [x] `rag_backup` : Export JSON complet (documents, metadatas, embeddings)
- [x] `rag_restore` : Import avec mode merge ou replace
- [x] Support multi-scope (project, global, all)
- [x] Embeddings sauvegardés pour restore rapide sans recalcul

---

## Phase 6 : Multi-modèle & Performance 🚀

**Objectif** : Plus rapide, plus flexible.

### Support multi-modèles
- [ ] `nomic-embed-text` (défaut, 274MB)
- [ ] `nomic-embed-text-v2-moe` (multilingual, 958MB)
- [ ] `mxbai-embed-large` (haute qualité, 670MB)
- [ ] `all-minilm` (tiny & fast, 46MB)

### Optimisations
- [ ] Batch embeddings (plusieurs chunks en un appel)
- [ ] Cache des embeddings fréquents
- [ ] Index incrémental (ne pas réindexer ce qui n'a pas changé)
- [ ] Async pour les gros indexages

### Métriques
- [ ] Temps d'indexation par fichier
- [ ] Temps de recherche moyen
- [ ] Taille de la DB
- [ ] Hit rate du cache

---

## Phase 7 : UI & DX 🎨

**Objectif** : Facile à utiliser et à debug.

### Web UI (optionnel)
- [ ] Dashboard pour voir les memories
- [ ] Search interactif
- [ ] Gestion des types/tags
- [ ] Stats visuelles
- [ ] Stack : FastAPI + HTMX (léger)

### TUI améliorée
- [ ] Vue des memories par type
- [ ] Delete/edit depuis la TUI
- [ ] Search en temps réel

### CLI amélioré
- [ ] `claude-rag init` : Setup initial
- [ ] `claude-rag doctor` : Check que tout est OK
- [ ] `claude-rag serve` : Lance le MCP server
- [ ] `claude-rag export --project=monprojet`

---

## Phase 8 : Communauté & Distribution 📦

**Objectif** : Facile à installer, facile à contribuer.

### Packaging
- [ ] Publier sur PyPI : `pip install claude-code-rag`
- [ ] Entry point : `claude-rag` disponible direct
- [ ] MCP installable via : `claude mcp add rag -- pip run claude-code-rag`

### Documentation
- [ ] README complet avec GIFs
- [ ] CONTRIBUTING.md
- [ ] Examples d'usage avancé
- [ ] Troubleshooting guide

### Médiatisation
- [ ] Post Reddit r/ClaudeAI
- [ ] Post Reddit r/LocalLLaMA
- [ ] Post Reddit r/selfhosted
- [ ] Article Medium/Dev.to
- [ ] Demo vidéo (30s GIF ou YouTube)

---

## Nice to Have (Backlog) 💭

- [ ] **Hybrid search** : Keyword + semantic combiné
- [ ] **Reranking** : Rerank les résultats avec un modèle dédié
- [ ] **Knowledge graph** : Relations entre memories
- [ ] **Multi-user** : Memories séparées par utilisateur
- [ ] **Encryption** : Chiffrer la DB locale
- [ ] **Cloud sync** : Sync optionnel vers un serveur (self-hosted)
- [ ] **MCP Resources** : Exposer les memories comme resources MCP
- [ ] **Prompts MCP** : Prompts prédéfinis pour les workflows courants

---

## Versioning

| Version | Milestone |
|---------|-----------|
| 0.1.0 | MCP server basique |
| 0.2.0 | Phase 2 - Multi-formats + chunking intelligent |
| 0.3.0 | Phase 3 - Memory types |
| 0.4.0 | Phase 4 - Auto-capture |
| 0.4.1 | Dual-scope memory (project + global) |
| 0.5.0 | Phase 5 - Export multi-format (AGENTS.md, CLAUDE.md, etc.) ✅ |
| 0.6.0 | Phase 5 - Sync bidirectionnelle (`rag_sync` + protection anti-boucle) ✅ |
| 0.7.0 | Phase 5 - Backup/Restore (`rag_backup`, `rag_restore`) ✅ |
| 1.0.0 | Stable, testé, documenté, sur PyPI |

---

## Priorités immédiates

1. ~~**Tests basiques**~~ ✅
2. ~~**Multi-formats**~~ ✅
3. ~~**Chunking markdown**~~ ✅
4. ~~**`rag_store` tool**~~ ✅
5. ~~**README avec GIF**~~ ✅
6. ~~**`rag_forget` tool**~~ ✅
7. ~~**Dual-scope memory**~~ ✅ (project + global)
8. ~~**`rag_list` tool**~~ ✅
9. ~~**Filtrage search**~~ ✅
10. ~~**`rag_capture` tool**~~ ✅ — Auto-capture sessions
11. ~~**`rag_export` tool**~~ ✅ — Multi-format export (AGENTS.md, CLAUDE.md, GEMINI.md...)
12. ~~**Sync bidirectionnelle**~~ ✅ — `rag_sync` + protection anti-boucle
13. ~~**Backup & Restore**~~ ✅ — `rag_backup` + `rag_restore`
14. **PyPI package** — Phase 8

---

**v0.7.0 shipped! 🚀**

New in v0.7.0:
- `rag_backup` - Full JSON export (documents, metadatas, embeddings)
- `rag_restore` - Import with merge or replace mode
- Embeddings saved for fast restore without recalculation

Previous (v0.6.0):
- `rag_sync` tool for bidirectional sync
- Hash-based change detection (SHA256)
- Protection against overwriting source files
