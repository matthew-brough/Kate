"""create reports table

Revision ID: c3d4e5f6a7b8
Revises:
Create Date: 2026-05-08 10:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "completed",
                "failed",
                name="reportstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reports_user_id"), "reports", ["user_id"], unique=False)
    op.create_index(op.f("ix_reports_status"), "reports", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reports_status"), table_name="reports")
    op.drop_index(op.f("ix_reports_user_id"), table_name="reports")
    op.drop_table("reports")
