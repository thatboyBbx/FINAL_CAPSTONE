"""
SQLAlchemy 2.0 models for document management, NER entities, and compliance checks.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Document(Base):
    """Core document record for every uploaded insurance document."""

    __tablename__ = "documents"

    id:                   Mapped[int]            = mapped_column(Integer, primary_key=True, index=True)
    title:                Mapped[str]            = mapped_column(String(255), nullable=False)
    original_filename:    Mapped[str]            = mapped_column(String(255), nullable=False)
    stored_filename:      Mapped[str]            = mapped_column(String(255), unique=True, nullable=False, index=True)
    file_path:            Mapped[str]            = mapped_column(String(500), nullable=False)
    mime_type:            Mapped[str]            = mapped_column(String(120), nullable=False)
    file_size:            Mapped[int]            = mapped_column(Integer, nullable=False)
    status:               Mapped[str]            = mapped_column(String(50), nullable=False, default="uploaded", index=True)
    document_category:    Mapped[str | None]     = mapped_column(String(100), nullable=True, index=True)
    notes:                Mapped[str | None]     = mapped_column(Text, nullable=True)
    uploaded_by_user_id:  Mapped[int]            = mapped_column(Integer, nullable=False, index=True)
    created_at:           Mapped[datetime]       = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Document classification — populated by DocumentClassifierService
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_method:     Mapped[str | None]   = mapped_column(String(20), nullable=True)
    classified_at:             Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # RAG indexing state
    rag_indexed:    Mapped[bool]            = mapped_column(Boolean, default=False, nullable=False)
    rag_indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    chunk_count:    Mapped[int]             = mapped_column(Integer, default=0, nullable=False)

    # Batch / Portfolio grouping
    portfolio_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    batch_id:     Mapped[int | None] = mapped_column(
        Integer, ForeignKey("processing_batches.id"), nullable=True
    )

    # Vault folder organisation (free-text, no FK table needed)
    folder:    Mapped[str | None] = mapped_column(String(255), nullable=True, default="Uncategorised", index=True)
    # Optional FK to clients table (populated when doc is linked to a client)
    client_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clients.id"), nullable=True, index=True)


class ExtractedEntity(Base):
    """
    Stores Named Entities extracted from insurance documents via NER.

    Each row represents one entity span identified within the document text.
    The ``start_char`` / ``end_char`` offsets are byte positions in the
    plain-text content returned by the PDF extractor, making it possible for
    the UI to re-highlight the exact passage.

    Active-learning columns (``is_correct`` … ``feedback_at``) are populated
    when a reviewer submits a correction through the UI; they are used for
    future model retraining.
    """

    __tablename__ = "extracted_entities"

    # ── Primary key ──────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Document reference ───────────────────────────────────────────────────
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False, index=True,
    )

    # ── Entity data ──────────────────────────────────────────────────────────
    entity_type:      Mapped[str]   = mapped_column(String(50), nullable=False, index=True)
    entity_value:     Mapped[str]   = mapped_column(Text, nullable=False)
    start_char:       Mapped[int]   = mapped_column(Integer, nullable=False)
    end_char:         Mapped[int]   = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)

    # ── Extraction timestamp ─────────────────────────────────────────────────
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    # ── Active-learning feedback (all nullable until a reviewer acts) ────────
    is_correct:          Mapped[bool | None]     = mapped_column(Boolean, nullable=True)
    corrected_type:      Mapped[str | None]      = mapped_column(String(50), nullable=True)
    corrected_value:     Mapped[str | None]      = mapped_column(Text, nullable=True)
    feedback_by_user_id: Mapped[int | None]      = mapped_column(Integer, nullable=True)
    feedback_at:         Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ComplianceCheck(Base):
    """
    Stores regulatory compliance check results for insurance documents.

    One row is written per compliance run.  The latest row for a document
    (ordered by ``checked_at`` desc) represents the current compliance state.
    JSON fields store arrays serialised as text so no additional migration is
    required on SQLite.
    """

    __tablename__ = "compliance_checks"

    # ── Primary key ──────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Document reference ───────────────────────────────────────────────────
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False, index=True,
    )

    # ── Compliance result ─────────────────────────────────────────────────────
    compliance_score: Mapped[float] = mapped_column(Float, nullable=False)
    status:           Mapped[str]   = mapped_column(String(20), nullable=False)

    # ── Mandatory clauses ─────────────────────────────────────────────────────
    mandatory_required: Mapped[int]        = mapped_column(Integer, nullable=False)
    mandatory_found:    Mapped[int]        = mapped_column(Integer, nullable=False)
    mandatory_missing:  Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Prohibited terms ──────────────────────────────────────────────────────
    prohibited_found:      Mapped[int]        = mapped_column(Integer, nullable=False, default=0)
    prohibited_violations: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Recommendations ───────────────────────────────────────────────────────
    recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Metadata ──────────────────────────────────────────────────────────────
    checked_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    checker_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
