"""rag_governance_schema

Adds deterministic RAG governance tables and columns:
  - document_chunks: chunk_text, page_estimate, section_label, word_count
  - retrieval_audit_log: new table (immutable event log for every governed RAG query)

Revision ID: a3f8c2e91b04
Revises: 9e599c7786d4
Create Date: 2026-05-29
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a3f8c2e91b04'
down_revision: Union[str, Sequence[str], None] = '942e478fe635'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = sa.inspect(bind).get_table_names()

    if "document_chunks" not in existing:
        # Table was never created by the baseline migration (models were not imported
        # in env.py at that time).  Create it now with all columns in one shot.
        op.create_table(
            "document_chunks",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("document_id", sa.Integer(), nullable=False, index=True),
            sa.Column("chunk_id", sa.String(200), nullable=False, unique=True),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("char_start", sa.Integer(), nullable=False),
            sa.Column("char_end", sa.Integer(), nullable=False),
            sa.Column("text_hash", sa.String(64), nullable=False),
            sa.Column("embedding_model", sa.String(200), nullable=False),
            sa.Column("embedding_version", sa.String(50), nullable=False),
            sa.Column("embedded_at", sa.DateTime(), nullable=False),
            sa.Column("chunk_text", sa.Text(), nullable=True),
            sa.Column("page_estimate", sa.Integer(), nullable=True),
            sa.Column("section_label", sa.String(100), nullable=True),
            sa.Column("word_count", sa.Integer(), nullable=True),
        )
        op.create_index("ix_doc_chunks_doc_id", "document_chunks", ["document_id"])
    else:
        # Table exists — add only the governance columns (may already exist on some DBs).
        cols = {c["name"] for c in sa.inspect(bind).get_columns("document_chunks")}
        with op.batch_alter_table("document_chunks") as batch_op:
            if "chunk_text" not in cols:
                batch_op.add_column(sa.Column("chunk_text", sa.Text(), nullable=True))
            if "page_estimate" not in cols:
                batch_op.add_column(sa.Column("page_estimate", sa.Integer(), nullable=True))
            if "section_label" not in cols:
                batch_op.add_column(sa.Column("section_label", sa.String(100), nullable=True))
            if "word_count" not in cols:
                batch_op.add_column(sa.Column("word_count", sa.Integer(), nullable=True))

    # -- retrieval_audit_log (create if absent) --
    op.create_table(
        "retrieval_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("queried_at", sa.DateTime(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("retrieval_method", sa.String(50), nullable=False, server_default="semantic"),
        sa.Column("chunks_retrieved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunks_above_threshold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("top_confidence", sa.Float(), nullable=True),
        sa.Column("mean_confidence", sa.Float(), nullable=True),
        sa.Column("answer_confidence", sa.Float(), nullable=True),
        sa.Column("embedding_model", sa.String(200), nullable=True),
        sa.Column("embedding_version", sa.String(50), nullable=True),
        sa.Column("chunk_ids_json", sa.Text(), nullable=True),
        sa.Column("hallucination_flags_json", sa.Text(), nullable=True),
        sa.Column("filters_applied_json", sa.Text(), nullable=True),
        sa.Column("answer_returned", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_index("ix_ral_id", "retrieval_audit_log", ["id"], unique=False)
    op.create_index("ix_ral_document_id", "retrieval_audit_log", ["document_id"], unique=False)
    op.create_index("ix_ral_queried_at", "retrieval_audit_log", ["queried_at"], unique=False)
    op.create_index("ix_ral_user_id", "retrieval_audit_log", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ral_user_id", table_name="retrieval_audit_log")
    op.drop_index("ix_ral_queried_at", table_name="retrieval_audit_log")
    op.drop_index("ix_ral_document_id", table_name="retrieval_audit_log")
    op.drop_index("ix_ral_id", table_name="retrieval_audit_log")
    op.drop_table("retrieval_audit_log")

    with op.batch_alter_table("document_chunks") as batch_op:
        batch_op.drop_column("word_count")
        batch_op.drop_column("section_label")
        batch_op.drop_column("page_estimate")
        batch_op.drop_column("chunk_text")
