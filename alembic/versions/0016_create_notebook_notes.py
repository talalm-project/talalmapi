"""create notebook notes

Revision ID: 0016_notebook_notes
Revises: 0015_notebook_followup_prompt
Create Date: 2026-05-25 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0016_notebook_notes"
down_revision = "0015_notebook_followup_prompt"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notebook_notes",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("notebook_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_context", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"]),
    )
    op.create_index("ix_notebook_notes_notebook_id", "notebook_notes", ["notebook_id"], unique=False)


def downgrade():
    op.drop_index("ix_notebook_notes_notebook_id", table_name="notebook_notes")
    op.drop_table("notebook_notes")
