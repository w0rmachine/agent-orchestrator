"""Add external/source fields to tasks.

Revision ID: 5b3a4c0d9b7d
Revises: edf7666e0198
Create Date: 2025-02-14
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5b3a4c0d9b7d"
down_revision = "edf7666e0198"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("source", sa.String(), nullable=False, server_default="manual"),
    )
    op.add_column(
        "tasks",
        sa.Column("external_id", sa.String(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("external_url", sa.String(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("external_project", sa.String(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("external_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "external_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(op.f("ix_tasks_source"), "tasks", ["source"], unique=False)
    op.create_index(
        op.f("ix_tasks_external_id"), "tasks", ["external_id"], unique=False
    )
    op.create_index(
        op.f("ix_tasks_external_project"), "tasks", ["external_project"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tasks_external_project"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_external_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_source"), table_name="tasks")
    op.drop_column("tasks", "external_deleted")
    op.drop_column("tasks", "external_updated_at")
    op.drop_column("tasks", "external_project")
    op.drop_column("tasks", "external_url")
    op.drop_column("tasks", "external_id")
    op.drop_column("tasks", "source")
