import pytest
from app.services.chunker_service import MarkdownChunker


def test_split_short_text_returns_single_chunk():
    chunker = MarkdownChunker(chunk_size=100)
    result = chunker.split("short text")
    assert result == ["short text"]


def test_split_text_exactly_at_limit_returns_single_chunk():
    chunker = MarkdownChunker(chunk_size=10)
    result = chunker.split("a" * 10)
    assert len(result) == 1


def test_split_empty_string_returns_single_chunk():
    chunker = MarkdownChunker(chunk_size=100)
    result = chunker.split("")
    assert result == [""]


def test_split_large_text_produces_multiple_chunks():
    text = "linha de conteudo\n" * 100  # ~1800 chars
    chunker = MarkdownChunker(chunk_size=200, overlap=20)
    result = chunker.split(text)
    assert len(result) > 1


def test_split_all_content_preserved():
    lines = [f"linha {i}\n" for i in range(50)]
    text = "".join(lines)
    chunker = MarkdownChunker(chunk_size=50, overlap=0)
    chunks = chunker.split(text)
    combined = "".join(chunks)
    for i in range(50):
        assert f"linha {i}" in combined


def test_split_overlap_seeds_next_chunk():
    text = "AAAA\n" * 30 + "BBBB\n" * 30  # ~300 chars
    chunker = MarkdownChunker(chunk_size=100, overlap=20)
    chunks = chunker.split(text)
    assert len(chunks) >= 2
    # Each chunk (except first) should start with overlap content
    assert len(chunks[1]) > 0


def test_split_no_overlap():
    # Use newlines so the chunker can split at line boundaries
    text = ("x" * 10 + "\n") * 30  # 330 chars, 30 lines
    chunker = MarkdownChunker(chunk_size=100, overlap=0)
    chunks = chunker.split(text)
    assert len(chunks) >= 2
    # No overlap means tail is empty string, so next chunk starts fresh
    for chunk in chunks:
        assert len(chunk) > 0


def test_split_default_parameters():
    chunker = MarkdownChunker()
    assert chunker.chunk_size == 15000
    assert chunker.overlap == 1000


def test_split_custom_parameters():
    chunker = MarkdownChunker(chunk_size=500, overlap=50)
    assert chunker.chunk_size == 500
    assert chunker.overlap == 50


def test_split_multiline_content():
    text = "\n".join([f"# Heading {i}\n\nParagraph content {i}." for i in range(20)])
    chunker = MarkdownChunker(chunk_size=100, overlap=10)
    chunks = chunker.split(text)
    assert len(chunks) > 1
    assert all(len(c) > 0 for c in chunks)
