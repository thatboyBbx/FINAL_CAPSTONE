"""add_missing_queue_and_auth_tables

Creates tables that were never added to app.db because their models were
not imported in alembic/env.py when the baseline migration ran:
  - queued_jobs
  - document_job_steps
  - dead_letter_jobs
  - refresh_tokens
  - access_token_blacklist
  - user_revocation_fence

Revision ID: b001_merge_heads_add_missing_tables
Revises: a3f8c2e91b04
Create Date: 2026-06-02
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b001_merge_heads_add_missing_tables"
down_revision: Union[str, Sequence[str], None] = "a3f8c2e91b04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    # ── queued_jobs ────────────────────────────────────────────────────────
    if "queued_jobs" not in existing:
        op.create_table(
            "queued_jobs",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("queue", sa.String(50), nullable=False, index=True),
            sa.Column("fn_name", sa.String(100), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="queued", index=True),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("document_id", sa.Integer(), nullable=True, index=True),
            sa.Column("step_name", sa.String(100), nullable=True),
            sa.Column("scheduled_for", sa.DateTime(), nullable=False, index=True),
            sa.Column("claimed_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("worker_id", sa.String(100), nullable=True),
            sa.Column("error_msg", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    # ── document_job_steps ────────────────────────────────────────────────
    if "document_job_steps" not in existing:
        op.create_table(
            "document_job_steps",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("document_id", sa.Integer(), nullable=False, index=True),
            sa.Column("batch_id", sa.Integer(), nullable=True, index=True),
            sa.Column("queue", sa.String(50), nullable=False),
            sa.Column("step_name", sa.String(100), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="queued", index=True),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("error_msg", sa.String(2000), nullable=True),
            sa.Column("queued_at", sa.DateTime(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("worker_id", sa.String(100), nullable=True),
            sa.Column("queued_job_id", sa.Integer(), nullable=True),
        )

    # ── dead_letter_jobs ──────────────────────────────────────────────────
    if "dead_letter_jobs" not in existing:
        op.create_table(
            "dead_letter_jobs",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("queue", sa.String(50), nullable=False, index=True),
            sa.Column("fn_name", sa.String(100), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=True, index=True),
            sa.Column("job_payload", sa.Text(), nullable=False),
            sa.Column("error_msg", sa.Text(), nullable=False),
            sa.Column("error_type", sa.String(200), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False),
            sa.Column("failed_at", sa.DateTime(), nullable=False, index=True),
            sa.Column("redriven", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("redriven_at", sa.DateTime(), nullable=True),
        )

    # ── refresh_tokens ────────────────────────────────────────────────────
    if "refresh_tokens" not in existing:
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("token_hash", sa.String(64), unique=True, nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), nullable=False, index=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("issued_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False, index=True),
            sa.Column("revoked", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_refresh_user_active", "refresh_tokens", ["user_id", "revoked"])

    # ── access_token_blacklist ────────────────────────────────────────────
    if "access_token_blacklist" not in existing:
        op.create_table(
            "access_token_blacklist",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("jti", sa.String(36), unique=True, nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), nullable=False, index=True),
            sa.Column("blacklisted_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
        )

    # ── user_revocation_fence ─────────────────────────────────────────────
    if "user_revocation_fence" not in existing:
        op.create_table(
            "user_revocation_fence",
            sa.Column("user_id", sa.Integer(), primary_key=True),
            sa.Column("tokens_valid_after", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for table in (
        "user_revocation_fence",
        "access_token_blacklist",
        "refresh_tokens",
        "dead_letter_jobs",
        "document_job_steps",
        "queued_jobs",
    ):
        if table in existing:
            op.drop_table(table)
