"""Add products.lifecycle (draft/active/retired)."""

from alembic import op
import sqlalchemy as sa

revision = "20261101_0009"
down_revision = "20260823_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "lifecycle",
            sa.String(length=16),
            nullable=False,
            server_default="draft",
        ),
    )
    op.create_index("ix_products_lifecycle", "products", ["lifecycle"], unique=False)
    op.execute(
        """
        UPDATE products
        SET lifecycle = CASE
            WHEN status IS TRUE THEN 'active'
            ELSE 'draft'
        END
        """
    )


def downgrade() -> None:
    op.drop_index("ix_products_lifecycle", table_name="products")
    op.drop_column("products", "lifecycle")
