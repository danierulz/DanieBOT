"""Remember extra provider URLs for a product that already exists."""

from alembic import op
import sqlalchemy as sa

revision = "20261117_0010"
down_revision = "20261101_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("product_source_urls"):
        return
    op.create_table(
        "product_source_urls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.product_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_url", name="uq_product_source_urls_source_url"),
    )
    op.create_index(
        "ix_product_source_urls_product_id",
        "product_source_urls",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_source_urls_product_id", table_name="product_source_urls")
    op.drop_table("product_source_urls")
