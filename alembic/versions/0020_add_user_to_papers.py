"""add user to papers

Revision ID: 0020_papers_user
Revises: 0019_create_papers
Create Date: 2026-06-24 00:00:00
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "0020_papers_user"
down_revision = "0019_create_papers"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("papers", sa.Column("user_id", sa.String(length=36), nullable=True))

    bind = op.get_bind()
    paper_count = bind.scalar(sa.text("SELECT COUNT(*) FROM papers"))
    if paper_count:
        owner_id = bind.scalar(sa.text("SELECT id FROM users ORDER BY created_at ASC LIMIT 1"))
        if owner_id is None:
            owner_id = str(uuid4())
            bind.execute(
                sa.text(
                    """
                    INSERT INTO users (
                        id,
                        email,
                        password_hash,
                        first_name,
                        last_name,
                        status,
                        role,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :id,
                        'papers-owner@example.com',
                        'unusable',
                        'Papers',
                        'Owner',
                        'active',
                        'admin',
                        now(),
                        now()
                    )
                    """
                ),
                {"id": owner_id},
            )

        bind.execute(sa.text("UPDATE papers SET user_id = :owner_id WHERE user_id IS NULL"), {"owner_id": owner_id})

    op.alter_column("papers", "user_id", existing_type=sa.String(length=36), nullable=False)
    op.create_index("ix_papers_user_id", "papers", ["user_id"], unique=False)
    op.create_foreign_key("fk_papers_user_id_users", "papers", "users", ["user_id"], ["id"])


def downgrade():
    op.drop_constraint("fk_papers_user_id_users", "papers", type_="foreignkey")
    op.drop_index("ix_papers_user_id", table_name="papers")
    op.drop_column("papers", "user_id")
