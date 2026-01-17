# Claude Code RAG - Roadmap

## Vision

Faire de claude-code-rag LA solution de mémoire persistante pour Claude Code : local-first, simple, et efficace.

---

## Phase 1 : Stabilisation & Polish ✅ → 🔄

**Objectif** : Un MCP server qui marche nickel out of the box.

### Done ✅
- [x] MCP server basique avec 3 tools
- [x] Intégration Ollama + ChromaDB
- [x] CLI standalone (`claude_rag.py`)
- [x] TUI avec Textual (`rag_tui.py`)

### À faire 🔄
- [ ] **Tests** : Ajouter des tests unitaires basiques
- [ ] **Error handling** : Meilleurs messages d'erreur (Ollama pas lancé, modèle pas pull, etc.)
- [ ] **Health check** : Tool `rag_health` pour vérifier que tout est OK
- [ ] **Logging** : Option debug pour troubleshoot
- [ ] **requirements.txt** : Ajouter `mcp` si manquant

---

## Phase 2 : Indexation Améliorée 📁

**Objectif** : Indexer plus que du markdown, de manière intelligente.

### Support multi-formats
- [ ] `.txt` — Texte brut
- [ ] `.py` — Code Python
- [ ] `.js` / `.ts` — JavaScript/TypeScript
- [ ] `.json` — Configs JSON
- [ ] `.yaml` / `.yml` — Configs YAML
- [ ] `.sh` — Scripts shell
- [ ] `.toml` — Configs TOML

### Chunking intelligent
- [ ] **Markdown** : Split par headers (`## Section`)
- [ ] **Code Python** : Split par fonctions/classes (`def`, `class`)
- [ ] **Code JS/TS** : Split par fonctions (`function`, `const`, `export`)
- [ ] **Configs** : Garder les blocs cohérents
- [ ] **Chunk overlap** : Ajouter un overlap de ~50 chars pour le contexte

### Métadonnées enrichies
- [ ] `file_type` : Extension du fichier
- [ ] `file_path` : Chemin complet
- [ ] `indexed_at` : Timestamp d'indexation
- [ ] `file_hash` : Hash pour détecter les changements
- [ ] `chunk_index` : Position dans le fichier

---

## Phase 3 : Memory Types & Organisation 🧠

**Objectif** : Pas juste "du texte", mais des types de mémoire structurés.

### Types de mémoire
- [ ] `context` — Contexte général (fichiers indexés)
- [ ] `decision` — Décisions techniques prises
- [ ] `bugfix` — Bugs résolus et solutions
- [ ] `architecture` — Choix d'architecture
- [ ] `preference` — Préférences utilisateur
- [ ] `snippet` — Bouts de code réutilisables

### Nouveau tool : `rag_store`
```python
rag_store(
    content: str,       # Le contenu à stocker
    memory_type: str,   # Type de mémoire
    tags: list[str],    # Tags optionnels
    project: str        # Projet associé
)
```

### Nouveau tool : `rag_forget`
```python
rag_forget(
    memory_id: str      # ID ou début d'ID
)
```

### Filtrage par type/projet
- [ ] Ajouter `memory_type` et `project` en filtre dans `rag_search`
- [ ] Tool `rag_list` pour lister les mémoires avec filtres

---

## Phase 4 : Auto-capture 🤖

**Objectif** : Capturer automatiquement le contexte des sessions Claude Code.

### Hook post-session
- [ ] Parser les fichiers `.jsonl` dans `~/.claude/projects/`
- [ ] Extraire les décisions importantes
- [ ] Résumer les sessions avec un LLM local (optionnel)
- [ ] Auto-index après chaque session

### Détection de patterns
- [ ] Détecter les phrases clés : "j'ai décidé", "on va utiliser", "le fix c'est"
- [ ] Marquer automatiquement le type de mémoire

### Config
```bash
# ~/.claude-rag/config.yaml
auto_capture:
  enabled: true
  session_summary: true  # Résumé auto des sessions
  watch_paths:
    - ~/projets/*/CLAUDE.md
```

---

## Phase 5 : Export & Sync 📤

**Objectif** : La mémoire doit pouvoir sortir du RAG.

### Export CLAUDE.md
- [ ] Tool `rag_export` : Générer un CLAUDE.md depuis les top memories
- [ ] Filtrer par projet/type
- [ ] Format markdown propre

### Sync bidirectionnelle
- [ ] Watch les CLAUDE.md et auto-réindexer
- [ ] Merge intelligent (pas de duplicatas)

### Backup & Restore
- [ ] `rag_backup` : Export JSON de toute la DB
- [ ] `rag_restore` : Import depuis backup
- [ ] Support versioning

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
| 0.1.0 | MCP server basique (actuel) |
| 0.2.0 | Phase 2 - Multi-formats + chunking intelligent |
| 0.3.0 | Phase 3 - Memory types |
| 0.4.0 | Phase 4 - Auto-capture |
| 0.5.0 | Phase 5 - Export & sync |
| 1.0.0 | Stable, testé, documenté, sur PyPI |

---

## Priorités immédiates (cette semaine)

1. **Tests basiques** — Que ça casse pas
2. **Multi-formats** — Au moins .txt, .py, .json
3. **Chunking markdown** — Split par `##`
4. **`rag_store` tool** — Stocker manuellement des memories
5. **README avec GIF** — Prêt pour Reddit

---

**Let's ship it! 🚀**
