"""baseline_full_schema_post_fix_campaign

Revision ID: 9e599c7786d4
Revises: 001_add_document_folder_client_id
Create Date: 2026-04-25 07:22:47.850164

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e599c7786d4'
down_revision: Union[str, Sequence[str], None] = '001_add_document_folder_client_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Baseline migration — ensures all tables exist post fix-campaign (Jobs A–E).
    Uses create_all with checkfirst=True so it is safe to run on any existing database.
    """
    from app.core.db import Base, engine
    Base.metadata.create_all(bind=engine, checkfirst=True)


def downgrade() -> None:
    """Baseline migrations are not reversible."""
    pass
