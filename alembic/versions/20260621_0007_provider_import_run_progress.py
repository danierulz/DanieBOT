"""Add phase and progress_detail to provider import runs."""

from alembic import op
import sqlalchemy as sa

revision = "20260621_0007"
down_revision = "20260621_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_import_runs",
        sa.Column("phase", sa.String(length=16), nullable=False, server_default="discovering"),
    )
    op.add_column(
        "provider_import_runs",
        sa.Column("progress_detail", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("provider_import_runs", "progress_detail")
    op.drop_column("provider_import_runs", "phase")
