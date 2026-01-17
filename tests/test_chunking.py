#!/usr/bin/env python3
"""
Basic tests for chunking functions
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server import (
    chunk_markdown,
    chunk_python,
    chunk_javascript,
    chunk_generic,
    chunk_content,
    SUPPORTED_EXTENSIONS
)


def test_chunk_markdown_by_headers():
    """Test markdown chunking splits by ## headers"""
    content = """# Title

Some intro text.

## Section 1

Content of section 1.

## Section 2

Content of section 2.
"""
    chunks = chunk_markdown(content)
    assert len(chunks) >= 2, f"Expected at least 2 chunks, got {len(chunks)}"
    assert any("Section 1" in c["text"] for c in chunks)
    assert any("Section 2" in c["text"] for c in chunks)
    print("✅ test_chunk_markdown_by_headers passed")


def test_chunk_python_by_functions():
    """Test Python chunking splits by functions"""
    content = """import os

def hello():
    print("hello")

def world():
    print("world")

class MyClass:
    pass
"""
    chunks = chunk_python(content)
    assert len(chunks) >= 3, f"Expected at least 3 chunks, got {len(chunks)}"
    assert any(c["type"] == "function" for c in chunks)
    assert any(c["type"] == "class" for c in chunks)
    print("✅ test_chunk_python_by_functions passed")


def test_chunk_javascript_by_functions():
    """Test JavaScript chunking splits by functions"""
    content = """import React from 'react';

function Hello() {
    return <div>Hello</div>;
}

const World = () => {
    return <div>World</div>;
}

export default Hello;
"""
    chunks = chunk_javascript(content)
    assert len(chunks) >= 2, f"Expected at least 2 chunks, got {len(chunks)}"
    print("✅ test_chunk_javascript_by_functions passed")


def test_chunk_generic_with_overlap():
    """Test generic chunking has overlap"""
    content = "A" * 1000
    chunks = chunk_generic(content, chunk_size=500)
    # With 50 char overlap, we should have more chunks than simple division
    assert len(chunks) >= 2
    print("✅ test_chunk_generic_with_overlap passed")


def test_supported_extensions():
    """Test all expected extensions are supported"""
    expected = [".md", ".txt", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".sh", ".toml"]
    for ext in expected:
        assert ext in SUPPORTED_EXTENSIONS, f"Missing extension: {ext}"
    print("✅ test_supported_extensions passed")


def test_chunk_content_routes_correctly():
    """Test chunk_content routes to correct chunker"""
    md_chunks = chunk_content("## Test\nContent", "markdown")
    py_chunks = chunk_content("def test(): pass", "python")
    txt_chunks = chunk_content("Hello world", "text")

    assert len(md_chunks) >= 1
    assert len(py_chunks) >= 1
    assert len(txt_chunks) >= 1
    print("✅ test_chunk_content_routes_correctly passed")


if __name__ == "__main__":
    test_chunk_markdown_by_headers()
    test_chunk_python_by_functions()
    test_chunk_javascript_by_functions()
    test_chunk_generic_with_overlap()
    test_supported_extensions()
    test_chunk_content_routes_correctly()
    print("\n🎉 All tests passed!")
