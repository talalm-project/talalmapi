"""make notebook note context nullable

Revision ID: 0017_note_context_nullable
Revises: 0016_notebook_notes
Create Date: 2026-05-25 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_note_context_nullable"
down_revision = "0016_notebook_notes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE notebook_notes SET is_context = NULL WHERE is_context = false")
    op.alter_column(
        "notebook_notes",
        "is_context",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )


def downgrade():
    op.execute("UPDATE notebook_notes SET is_context = false WHERE is_context IS NULL")
    op.alter_column(
        "notebook_notes",
        "is_context",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    )
