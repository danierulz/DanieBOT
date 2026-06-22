"""Widen products.description to 1024 characters."""

from alembic import op
import sqlalchemy as sa

revision = "20260621_0006"
down_revision = "20260621_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "products",
        "description",
        existing_type=sa.String(length=255),
        type_=sa.String(length=1024),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "products",
        "description",
        existing_type=sa.String(length=1024),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
