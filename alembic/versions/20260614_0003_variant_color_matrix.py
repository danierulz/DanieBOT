"""Add color_id to product_variants for color-size stock matrix."""

from alembic import op
import sqlalchemy as sa

revision = "20260614_0003"
down_revision = "20260528_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_variants",
        sa.Column("color_id", sa.Integer(), sa.ForeignKey("colors.color_id"), nullable=True),
    )
    op.create_index("ix_product_variants_color_id", "product_variants", ["color_id"], unique=False)
    op.drop_constraint("uq_product_variants_product_size", "product_variants", type_="unique")
    op.create_unique_constraint(
        "uq_product_variants_product_size_color",
        "product_variants",
        ["product_id", "size_id", "color_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_product_variants_product_size_color", "product_variants", type_="unique")
    op.create_unique_constraint(
        "uq_product_variants_product_size",
        "product_variants",
        ["product_id", "size_id"],
    )
    op.drop_index("ix_product_variants_color_id", table_name="product_variants")
    op.drop_column("product_variants", "color_id")
