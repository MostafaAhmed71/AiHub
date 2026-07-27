"""Unit tests for chunking + prompt rendering (no external services)."""

import pytest

from app.services.chunking import chunk_text, extract_text
from app.services.prompts import PromptService


def test_extract_txt():
    text = extract_text("notes.txt", b"Hello AI Hub\nSecond line")
    assert "Hello AI Hub" in text
    assert "Second line" in text


def test_extract_csv():
    raw = b"name,score\nAlice,10\nBob,9\n"
    text = extract_text("scores.csv", raw)
    assert "Alice" in text
    assert "Bob" in text


def test_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported"):
        extract_text("photo.png", b"not-an-image")


def test_chunk_text_overlap():
    text = " ".join(f"word{i}" for i in range(200))
    chunks = chunk_text(text, chunk_size=80, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 120 for c in chunks)  # soft upper bound with break logic


def test_chunk_short_text_single():
    assert chunk_text("short", chunk_size=100) == ["short"]


def test_chunk_empty():
    assert chunk_text("   \n  ") == []


def test_prompt_render():
    rendered = PromptService.render(
        "Hello {{ name }}, welcome to {{product}}",
        {"name": "Sara", "product": "School"},
    )
    assert rendered == "Hello Sara, welcome to School"


def test_prompt_render_missing_var():
    with pytest.raises(ValueError, match="Missing variable"):
        PromptService.render("Hi {{name}}", {})
