"""
SQLAlchemy model for persisting chunk metadata alongside ChromaDB embeddings.

Each DocumentChunk row mirrors one ChromaDB entry.  Storing metadata here enables:
  - version tracking (embedding_model / embedding_version per chunk)
  - stale-detection queries without touching ChromaDB
  - text-hash-based change detection for selective re-embedding
  - lifecycle management (delete-and-replace on reindex)
  - source traceability (chunk_text stored for provenance without ChromaDB)
  - human-readable location (page_estimate, section_label)

chunk_id matches the ChromaDB document ID: "{document_id}_chunk_{chunk_index}".
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id:                Mapped[int]           = mapped_column(Integer, primary_key=True, index=True)
    document_id:       Mapped[int]           = mapped_column(Integer, nullable=False, index=True)
    chunk_id:          Mapped[str]           = mapped_column(String(200), nullable=False, unique=True)
    chunk_index:       Mapped[int]           = mapped_column(Integer, nullable=False)
    char_start:        Mapped[int]           = mapped_column(Integer, nullable=False)
    char_end:          Mapped[int]           = mapped_column(Integer, nullable=False)
    text_hash:         Mapped[str]           = mapped_column(String(64), nullable=False)
    embedding_model:   Mapped[str]           = mapped_column(String(200), nullable=False)
    embedding_version: Mapped[str]           = mapped_column(String(50), nullable=False)
    embedded_at:       Mapped[datetime]      = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Source traceability — stored so citations can be resolved without re-querying ChromaDB
    chunk_text:        Mapped[str | None]    = mapped_column(Text, nullable=True)

    # Human-readable location hints derived at index time
    page_estimate:     Mapped[int | None]    = mapped_column(Integer, nullable=True)
    section_label:     Mapped[str | None]    = mapped_column(String(100), nullable=True)
    word_count:        Mapped[int | None]    = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_doc_chunks_doc_id", "document_id"),
    )
