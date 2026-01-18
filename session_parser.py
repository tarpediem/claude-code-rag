#!/usr/bin/env python3
"""
Claude Code Session Parser
Parses .jsonl session files and extracts meaningful content for RAG indexing.
"""
import json
import logging
import re
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional

# Security constants
MAX_LINE_SIZE = 1_000_000  # 1MB per line
MAX_FILE_SIZE = 100_000_000  # 100MB per file


@dataclass
class ExtractedMemory:
    """A piece of information extracted from a session"""
    content: str
    memory_type: str  # decision, bugfix, architecture, preference, snippet, context
    source: str  # session file path
    timestamp: str
    confidence: float  # 0-1, how confident we are about the classification
    tags: list[str]


# Patterns for detecting memory types
DECISION_PATTERNS = [
    r"(?:j'ai |on a |we )?(décidé|decided|choisi|chose|chosen|opté|opted)",
    r"(?:on va |we will |let's )?(utiliser|use|prendre|take|aller avec|go with)",
    r"(?:the |la |le )?(solution|approche|approach|stratégie|strategy) (?:est|is|sera|will be)",
    r"(?:j'|I )?(?:préfère|prefer|recommande|recommend)",
    r"(?:on |we )?(?:part|go) (?:sur|with|for)",
]

BUGFIX_PATTERNS = [
    r"(?:le |the )?(?:fix|correctif|solution|problème résolu|problem solved)",
    r"(?:j'ai |I )?(?:fixé|fixed|corrigé|corrected|résolu|resolved|réparé|repaired)",
    r"(?:le |the )?(?:bug|erreur|error|issue) (?:était|was|venait|came from)",
    r"(?:ça |it )?(?:marche|works) (?:maintenant|now)",
    r"(?:le |the )?(?:problème|problem|issue) (?:c'était|was|est|is)",
]

ARCHITECTURE_PATTERNS = [
    r"(?:l'|the )?architecture",
    r"(?:la |the )?structure (?:du |of the )?(?:projet|project|code)",
    r"(?:le |the )?(?:design|pattern|modèle)",
    r"(?:on |we )?(?:organise|organize|structure)",
    r"(?:les |the )?(?:composants|components|modules|services)",
]

PREFERENCE_PATTERNS = [
    r"(?:je |I )?(?:préfère|prefer|aime|like|veux|want)",
    r"(?:toujours |always )(?:utiliser|use|faire|do)",
    r"(?:ne |don't )(?:jamais|never)",
    r"(?:par défaut|by default)",
    r"(?:ma |my )?(?:règle|rule|convention)",
]

SNIPPET_PATTERNS = [
    r"```[\w]*\n",  # Code blocks
    r"(?:voici|here's|here is) (?:le |the )?(?:code|script|commande|command)",
    r"(?:exemple|example|sample):",
]


def detect_memory_type(text: str) -> tuple[str, float]:
    """
    Detect the type of memory based on content patterns.
    Returns (type, confidence)
    """
    text_lower = text.lower()

    # Check each pattern category
    for pattern in DECISION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return "decision", 0.8

    for pattern in BUGFIX_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return "bugfix", 0.8

    for pattern in ARCHITECTURE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return "architecture", 0.7

    for pattern in PREFERENCE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return "preference", 0.7

    for pattern in SNIPPET_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return "snippet", 0.6

    return "context", 0.5


def extract_tags(text: str) -> list[str]:
    """Extract relevant tags from text"""
    tags = []

    # Tech keywords to look for
    tech_keywords = [
        "python", "javascript", "typescript", "rust", "go", "java",
        "docker", "kubernetes", "k8s", "nginx", "postgres", "postgresql",
        "mysql", "redis", "mongodb", "sqlite", "git", "github",
        "api", "rest", "graphql", "grpc", "http", "https",
        "linux", "windows", "macos", "ubuntu", "debian", "arch", "cachyos",
        "npm", "pip", "cargo", "pacman", "apt", "brew",
        "react", "vue", "angular", "svelte", "nextjs", "fastapi", "flask", "django",
        "ollama", "rocm", "cuda", "gpu", "cpu", "ram", "nvme", "ssd",
        "systemd", "grub", "kernel", "bios", "uefi",
    ]

    text_lower = text.lower()
    for keyword in tech_keywords:
        if keyword in text_lower:
            tags.append(keyword)

    return tags[:5]  # Limit to 5 tags


def parse_session_file(filepath: Path) -> Iterator[ExtractedMemory]:
    """
    Parse a Claude Code session .jsonl file and extract memories.
    Yields ExtractedMemory objects.
    """
    if not filepath.exists():
        return

    # Security: reject symlinks
    if filepath.is_symlink():
        logging.warning(f"Skipping symlink: {filepath}")
        return

    # Security: check file size
    try:
        file_size = filepath.stat().st_size
        if file_size > MAX_FILE_SIZE:
            logging.warning(f"Skipping large file ({file_size} bytes): {filepath}")
            return
    except OSError:
        return

    with open(filepath, 'r') as f:
        for line_num, line in enumerate(f):
            # Security: check line size
            if len(line) > MAX_LINE_SIZE:
                logging.warning(f"Skipping large line {line_num} in {filepath}")
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Security: validate message structure
            if not isinstance(msg, dict):
                continue

            msg_type = msg.get("type")

            # Process assistant messages
            if msg_type == "assistant":
                content_blocks = msg.get("message", {}).get("content", [])
                timestamp = msg.get("timestamp", datetime.now().isoformat())

                for block in content_blocks:
                    if block.get("type") == "text":
                        text = block.get("text", "")
                        if len(text) > 50:  # Skip very short messages
                            mem_type, confidence = detect_memory_type(text)
                            if confidence >= 0.7:  # Only extract high-confidence memories
                                yield ExtractedMemory(
                                    content=text[:2000],  # Limit size
                                    memory_type=mem_type,
                                    source=str(filepath),
                                    timestamp=timestamp,
                                    confidence=confidence,
                                    tags=extract_tags(text)
                                )

            # Process summaries (these are high-value)
            elif msg_type == "summary":
                summary = msg.get("summary", "")
                if summary:
                    yield ExtractedMemory(
                        content=f"Session summary: {summary}",
                        memory_type="context",
                        source=str(filepath),
                        timestamp=datetime.now().isoformat(),
                        confidence=0.9,
                        tags=extract_tags(summary)
                    )


def get_all_sessions(projects_dir: Optional[Path] = None) -> list[Path]:
    """Get all session files from Claude Code projects directory"""
    if projects_dir is None:
        projects_dir = Path.home() / ".claude" / "projects"

    if not projects_dir.exists():
        return []

    sessions = []
    for project_dir in projects_dir.iterdir():
        # Security: reject symlinked directories
        if project_dir.is_dir() and not project_dir.is_symlink():
            for session_file in project_dir.glob("*.jsonl"):
                # Security: reject symlinked files
                if not session_file.is_symlink():
                    sessions.append(session_file)

    return sorted(sessions, key=lambda p: p.stat().st_mtime, reverse=True)


def parse_recent_sessions(
    max_sessions: int = 5,
    projects_dir: Optional[Path] = None
) -> Iterator[ExtractedMemory]:
    """Parse the most recent sessions and yield memories"""
    sessions = get_all_sessions(projects_dir)[:max_sessions]

    for session_file in sessions:
        yield from parse_session_file(session_file)


if __name__ == "__main__":
    # Test the parser
    print("Parsing recent Claude Code sessions...\n")

    memories_by_type = {}
    for memory in parse_recent_sessions(max_sessions=3):
        mem_type = memory.memory_type
        if mem_type not in memories_by_type:
            memories_by_type[mem_type] = []
        memories_by_type[mem_type].append(memory)

    for mem_type, memories in sorted(memories_by_type.items()):
        print(f"\n=== {mem_type.upper()} ({len(memories)}) ===")
        for mem in memories[:3]:  # Show first 3 of each type
            print(f"\n[{mem.confidence:.1f}] {mem.content[:150]}...")
            if mem.tags:
                print(f"    Tags: {', '.join(mem.tags)}")
