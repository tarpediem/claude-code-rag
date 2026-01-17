#!/usr/bin/env python3
"""
Claude Code RAG - Simple RAG with Ollama embeddings + ChromaDB
Minimaliste et efficace pour Claude Code memory
"""
import chromadb
import requests
import os
import hashlib
import time
from pathlib import Path

# Configuration
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
CHROMA_PATH = os.environ.get("CHROMA_PATH", os.path.expanduser("~/.local/share/claude-memory"))


def get_embedding(text: str) -> list:
    """Get embedding from Ollama"""
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text}
    )
    return resp.json()["embedding"]


def get_embeddings_batch(texts: list) -> list:
    """Get embeddings for multiple texts"""
    return [get_embedding(t) for t in texts]


class SimpleRAG:
    def __init__(self, collection_name: str = "claude_memory"):
        os.makedirs(CHROMA_PATH, exist_ok=True)
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_document(self, filepath: str, chunk_size: int = 500):
        """Index a document"""
        path = Path(filepath)
        content = path.read_text()
        doc_id = hashlib.md5(filepath.encode()).hexdigest()[:8]

        # Simple chunking
        chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]

        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        embeddings = get_embeddings_batch(chunks)
        metadatas = [{"source": filepath, "chunk": i} for i in range(len(chunks))]

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )
        return len(chunks)

    def search(self, query: str, n_results: int = 3) -> list:
        """Search for relevant chunks"""
        query_embedding = get_embedding(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        return [
            {"text": doc, "source": meta["source"], "score": 1-dist}
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            )
        ]

    def stats(self):
        """Get collection stats"""
        return {
            "total_chunks": self.collection.count(),
            "path": CHROMA_PATH
        }


def main():
    import sys
    rag = SimpleRAG()

    if len(sys.argv) < 2:
        print("Claude Code RAG - Simple semantic search for your codebase")
        print("")
        print("Usage:")
        print("  claude-rag index <file_or_dir>  - Index markdown files")
        print("  claude-rag search <query>       - Semantic search")
        print("  claude-rag stats                - Show stats")
        print("")
        print("Environment variables:")
        print("  OLLAMA_URL   - Ollama server URL (default: http://localhost:11434)")
        print("  EMBED_MODEL  - Embedding model (default: nomic-embed-text)")
        print("  CHROMA_PATH  - Database path (default: ~/.local/share/claude-memory)")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "index":
        path = Path(sys.argv[2])
        start = time.time()
        if path.is_dir():
            total = 0
            for f in path.glob("**/*.md"):
                chunks = rag.add_document(str(f))
                print(f"Indexed {f.name}: {chunks} chunks")
                total += chunks
            print(f"Total: {total} chunks in {time.time()-start:.2f}s")
        else:
            chunks = rag.add_document(str(path))
            print(f"Indexed {path.name}: {chunks} chunks in {time.time()-start:.2f}s")

    elif cmd == "search":
        query = " ".join(sys.argv[2:])
        start = time.time()
        results = rag.search(query)
        print(f"Search completed in {time.time()-start:.2f}s\n")
        for i, r in enumerate(results, 1):
            print(f"[{i}] Score: {r['score']:.3f} | Source: {r['source']}")
            print(f"    {r['text'][:200]}...")
            print()

    elif cmd == "stats":
        stats = rag.stats()
        print(f"Total chunks: {stats['total_chunks']}")
        print(f"Database path: {stats['path']}")


if __name__ == "__main__":
    main()
