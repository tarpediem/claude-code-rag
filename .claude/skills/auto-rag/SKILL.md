---
name: "Auto RAG Memory"
description: "Automatically store important decisions, bug fixes, code snippets, and architecture changes in the RAG memory system during development work. Activates whenever coding, debugging, or making technical decisions."
---

# 🧠 Automatic RAG Memory Storage

## Purpose

This skill ensures that Claude **systematically stores** important information in the RAG memory system **during development**, not just at the end. This creates a persistent knowledge base that grows with every session.

## When This Skill Activates

This skill should activate during:
- Coding and development work
- Bug fixing and debugging
- Architecture decisions
- Creating reusable code snippets
- Making technical choices
- Refactoring or redesigning

## Core Rules

### 1. Store as You Work (Not After)

**CRITICAL**: Use `rag_store` IMMEDIATELY when:

- 🎯 **Decision made**: Technical choice, library selection, approach chosen
  ```
  rag_store(content="DECISION: Chose X over Y because...", memory_type="decision", tags=[...])
  ```

- 🐛 **Bug fixed**: Problem solved with solution details
  ```
  rag_store(content="BUG FIXED: Problem was X, solution was Y", memory_type="bugfix", tags=[...])
  ```

- 📝 **Useful snippet created**: Reusable code, config, or command
  ```
  rag_store(content="SNIPPET: [description]\n\n```language\n[code]\n```", memory_type="snippet", tags=[...])
  ```

- 🏗️ **Architecture changed**: System design, structure, patterns
  ```
  rag_store(content="ARCHITECTURE: Changed from X to Y pattern...", memory_type="architecture", tags=[...])
  ```

- ⚙️ **User preference identified**: Workflow, style, requirements
  ```
  rag_store(content="PREFERENCE: User wants X instead of Y", memory_type="preference", tags=[...])
  ```

### 2. Start Every Session with Search

Before starting work, check existing context:
```
rag_search(query="relevant keywords", scope="all", compact=true)
```

**IMPORTANT: Use `compact=true` by default** to save tokens (recommended for Claude Pro users).
Only use `compact=false` when you need full context details.

This prevents:
- Repeating previous mistakes
- Redoing solved problems
- Ignoring established preferences
- Missing important context

**Token optimization:**
- `compact=true`: ~60 chars per result (saves 66% tokens)
- `compact=false`: ~300 chars per result (use only when needed)

### 3. Progressive Storage Pattern

**During a typical development session:**

1. **Start**: `rag_search` for context on the task
2. **While coding**: `rag_store` each decision/fix/snippet as it happens
3. **After significant changes**: `rag_sync` if CLAUDE.md was modified
4. **Never**: Wait until the end to batch-store everything

### 4. Quality Over Quantity

Store items that are:
- ✅ Reusable in future sessions
- ✅ Non-obvious solutions
- ✅ Important architectural decisions
- ✅ User-specific preferences
- ✅ Bug fixes with context

Don't store:
- ❌ Trivial changes
- ❌ Obvious solutions
- ❌ Temporary debugging
- ❌ Work-in-progress code

## Scope Selection

- **project**: Project-specific knowledge (most common)
- **global**: Cross-project knowledge (tools, patterns, user preferences)

## Tag Guidelines

Use descriptive tags for better searchability:
- Technology/language: `["python", "fastapi", "html"]`
- Domain: `["web-ui", "installation", "automation"]`
- Platform: `["linux", "windows", "cross-platform"]`

## Example Workflow

```markdown
User: "Add a dark mode toggle to the dashboard"

Claude:
1. rag_search(query="dark mode theme switching", scope="project", compact=true)
   → Check if we've implemented theme switching before

2. [Implements solution]

3. rag_store(
     content="DECISION: Dark mode implementation using CSS variables...",
     memory_type="decision",
     scope="project",
     tags=["web-ui", "dark-mode", "css"]
   )
   → Store immediately after making the decision

4. [Creates reusable toggle component]

5. rag_store(
     content="SNIPPET: Dark mode toggle component\n\n```javascript\n...\n```",
     memory_type="snippet",
     scope="project",
     tags=["react", "toggle", "component"]
   )
   → Store the reusable code
```

## Anti-Pattern (Don't Do This)

❌ **Wrong**: Work on 5 features, fix 3 bugs, make 10 decisions, then at the end:
```
"Let me store everything in the RAG now..."
rag_store(...) × 18 times
```

✅ **Correct**: Store each important item immediately when it happens during development.

## Remember

The RAG is a **working tool**, not a documentation tool. Use it **during** development to build a knowledge base that helps in future sessions. Every stored memory makes the next session smarter.
