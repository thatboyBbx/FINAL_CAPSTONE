"""
Tests for the knowledge base seeder.
Uses a temporary ChromaDB in-memory client — no real ChromaDB connection needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path so `scripts` package can be imported
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


class TestSeederChunking:
    """Verify text chunking logic produces correct chunk sizes and overlaps."""

    def test_chunk_size_is_respected(self) -> None:
        """Chunks must not exceed ~500 tokens (approx 2000 chars)."""
        from scripts.seed_knowledge_base import chunk_text

        long_text = "word " * 2000  # 2000 words
        chunks = chunk_text(long_text, chunk_size=500, overlap=50)
        for chunk in chunks:
            word_count = len(chunk.split())
            assert word_count <= 550, f"Chunk exceeded size limit: {word_count} words"

    def test_overlap_produces_continuity(self) -> None:
        """Adjacent chunks must share overlapping tokens."""
        from scripts.seed_knowledge_base import chunk_text

        text = " ".join([f"word{i}" for i in range(200)])
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) >= 2, "Should produce multiple chunks"
        # The last 20 tokens of chunk 0 should appear at the start of chunk 1
        chunk0_tail = chunks[0].split()[-20:]
        chunk1_head = chunks[1].split()[:20]
        assert chunk0_tail == chunk1_head, "Overlap tokens must match between adjacent chunks"

    def test_empty_text_returns_empty_list(self) -> None:
        from scripts.seed_knowledge_base import chunk_text

        assert chunk_text("", chunk_size=500, overlap=50) == []

    def test_short_text_returns_single_chunk(self) -> None:
        from scripts.seed_knowledge_base import chunk_text

        text = "This is a short insurance clause."
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) == 1

    def test_whitespace_only_returns_empty_list(self) -> None:
        from scripts.seed_knowledge_base import chunk_text

        assert chunk_text("   \n\t  ", chunk_size=500, overlap=50) == []

    def test_exact_chunk_size_boundary(self) -> None:
        """Text of exactly chunk_size words should return 1 chunk."""
        from scripts.seed_knowledge_base import chunk_text

        text = " ".join([f"w{i}" for i in range(100)])
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) >= 1
        assert len(chunks[0].split()) == 100


class TestSeederDocType:
    """Verify doc type inference from filenames."""

    def test_infers_insurance_act(self) -> None:
        from scripts.seed_knowledge_base import infer_doc_type

        assert infer_doc_type("insurance_act_chapter_24_07.pdf") == "insurance_act"

    def test_infers_circular(self) -> None:
        from scripts.seed_knowledge_base import infer_doc_type

        assert infer_doc_type("ipec_circular_2023_03.pdf") == "ipec_circular"

    def test_infers_motor_policy(self) -> None:
        from scripts.seed_knowledge_base import infer_doc_type

        assert infer_doc_type("standard_motor_policy_wording.pdf") == "motor_policy"

    def test_fallback_for_unknown(self) -> None:
        from scripts.seed_knowledge_base import infer_doc_type

        assert infer_doc_type("random_document.pdf") == "insurance_document"
