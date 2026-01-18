# Claude Code RAG

> **Donne une mémoire persistante à Claude Code** - Recherche sémantique locale avec Ollama + ChromaDB

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

## Pourquoi ?

Claude Code oublie tout entre les sessions. Ton fichier `CLAUDE.md` grossit, mais chercher dedans c'est la galère.

**claude-code-rag** donne une mémoire sémantique à Claude Code :
- Indexe tes docs, configs et code
- Recherche par sens, pas par mots-clés
- Retient les décisions, bugfixes et choix d'architecture
- 100% local - pas de cloud, pas de clés API

## Fonctionnalités

- **Recherche sémantique** - Trouve le contexte pertinent même avec des mots différents
- **Chunking intelligent** - Découpe le markdown par headers, Python par fonctions, JS par exports
- **Multi-format** - `.md`, `.txt`, `.py`, `.js`, `.ts`, `.json`, `.yaml`, `.sh`, `.toml`
- **Types de mémoire** - Tag tes memories : `decision`, `bugfix`, `architecture`, `snippet`...
- **Double scope** - 📁 Mémoires par projet + 🌐 Globales (système)
- **Intégration MCP** - Outils natifs Claude Code, pas besoin de bash
- **Rapide** - ~30ms recherche, ~1s/fichier indexation sur iGPU AMD

## Démarrage rapide

```bash
# 1. Clone
git clone https://github.com/tarpediem/claude-code-rag.git
cd claude-code-rag

# 2. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Pull le modèle d'embedding
ollama pull nomic-embed-text

# 4. Test
python claude_rag.py index ~/CLAUDE.md
python claude_rag.py search "comment configurer le GPU"
```

## Intégration MCP (Recommandé)

Ajoute dans `~/.claude.json` sous ton projet :

```json
{
  "mcpServers": {
    "claude-rag": {
      "command": "/chemin/vers/venv/bin/python",
      "args": ["/chemin/vers/mcp_server.py"]
    }
  }
}
```

Relance Claude Code. T'as maintenant 13 outils natifs :

| Outil | Description |
|-------|-------------|
| `rag_search` | Recherche sémantique (avec filtre par type) |
| `rag_index` | Indexer fichiers ou dossiers |
| `rag_store` | Stocker manuellement une mémoire avec type/tags |
| `rag_sync` | Synchroniser les fichiers surveillés |
| `rag_capture` | Auto-capture depuis les sessions Claude Code |
| `rag_export` | Exporter vers AGENTS.md/CLAUDE.md/GEMINI.md etc. |
| `rag_list` | Lister les mémoires avec filtres |
| `rag_forget` | Supprimer des mémoires par requête ou ID |
| `rag_backup` | Exporter toutes les mémoires en JSON |
| `rag_restore` | Restaurer depuis un backup JSON |
| `rag_reset` | Vider la base de données (avec confirmation) |
| `rag_stats` | Afficher les statistiques |
| `rag_health` | Vérifier le statut Ollama/ChromaDB |

## Auto-RAG dans CLAUDE.md (Recommandé)

Ajoute ça dans ton `CLAUDE.md` pour que Claude utilise **automatiquement** le RAG :

```markdown
## RAG Local (UTILISER AUTOMATIQUEMENT)

Un système RAG est disponible via MCP. **Tu DOIS l'utiliser PROACTIVEMENT** :

### Quand utiliser le RAG :
- **TOUJOURS chercher d'abord** → `rag_search` AVANT de demander quoi que ce soit
- **Contexte sur n'importe quel sujet** → Le RAG contient l'historique de tout
- **Problème/bug** → Vérifier si on l'a déjà résolu avant
- **Préférences utilisateur** → Les choix passés sont dans le RAG

### Maintenance :
- **Début de session** : `rag_sync` pour synchroniser ce fichier
- **Après modif de ce fichier** : `rag_sync` pour mettre à jour l'index
- **Nouvelle décision importante** : `rag_store` pour la sauvegarder
```

## Scopes de mémoire

| Scope | Icône | Description |
|-------|-------|-------------|
| `project` | 📁 | Mémoires spécifiques au projet (défaut pour store/index) |
| `global` | 🌐 | Connaissances système (ta machine, préférences) |
| `all` | | Les deux scopes (défaut pour search/list) |

## Configuration

| Variable d'env | Défaut | Description |
|----------------|--------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Serveur Ollama |
| `EMBED_MODEL` | `nomic-embed-text` | Modèle d'embedding |
| `CHROMA_PATH` | `~/.local/share/claude-memory` | Chemin de la DB |

## Performance

Testé sur AMD Radeon 890M (iGPU) avec ROCm :

| Opération | Vitesse |
|-----------|---------|
| Recherche | ~30ms |
| Indexation | ~1s/fichier |
| Embedding | ~100 tok/s |

## Licence

MIT

---

**Fait pour la communauté [Claude Code](https://claude.ai/code)**
