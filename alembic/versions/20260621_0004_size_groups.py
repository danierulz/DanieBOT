"""Add size_group to sizes and categories."""

from alembic import op
import sqlalchemy as sa

revision = "20260621_0004"
down_revision = "20260614_0003"
branch_labels = None
depends_on = None

_NUMERIC_CODES = ("34", "36", "38", "40", "42")
_NUMERIC_CATEGORIES = ("jeans", "pantalones")


def upgrade() -> None:
    op.add_column(
        "sizes",
        sa.Column("size_group", sa.String(length=16), nullable=False, server_default="letter"),
    )
    op.add_column(
        "categories",
        sa.Column("size_group", sa.String(length=16), nullable=False, server_default="letter"),
    )

    conn = op.get_bind()
    for code in _NUMERIC_CODES:
        conn.execute(
            sa.text("UPDATE sizes SET size_group = 'numeric' WHERE code = :code"),
            {"code": code},
        )
    for slug in _NUMERIC_CATEGORIES:
        conn.execute(
            sa.text("UPDATE categories SET size_group = 'numeric' WHERE slug = :slug"),
            {"slug": slug},
        )


def downgrade() -> None:
    op.drop_column("categories", "size_group")
    op.drop_column("sizes", "size_group")
