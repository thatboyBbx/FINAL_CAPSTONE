"""add_document_folder_client_id

Revision ID: 001_add_document_folder_client_id
Revises:
Create Date: 2026-04-13

Adds two columns to the documents table:
  - folder    (String 255, nullable, default "Uncategorised") — vault folder label
  - client_id (Integer, nullable, FK → clients.id)           — optional client link
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "001_add_document_folder_client_id"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add folder and client_id columns to the documents table."""
    # Add folder column with a default value for existing rows
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(
            sa.Column(
                "folder",
                sa.String(255),
                nullable=True,
                server_default="Uncategorised",
            )
        )
        batch_op.add_column(
            sa.Column(
                "client_id",
                sa.Integer(),
                sa.ForeignKey("clients.id"),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Remove the added columns from the documents table."""
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("folder")
        batch_op.drop_column("client_id")
