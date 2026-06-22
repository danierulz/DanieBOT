"""Provider import tracking and product provider fields."""

from alembic import op
import sqlalchemy as sa

revision = "20260621_0005"
down_revision = "20260621_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("provider", sa.String(length=32), nullable=True))
    op.add_column("products", sa.Column("provider_source_url", sa.String(length=512), nullable=True))
    op.create_index("ix_products_provider", "products", ["provider"], unique=False)
    op.create_index("ix_products_cod_product", "products", ["cod_product"], unique=True)

    op.create_table(
        "provider_import_runs",
        sa.Column("run_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("triggered_by", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_provider_import_runs_provider", "provider_import_runs", ["provider"], unique=False)

    op.create_table(
        "provider_import_run_items",
        sa.Column("item_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=False),
        sa.Column("cod_product", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["provider_import_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("item_id"),
    )
    op.create_index(
        "ix_provider_import_run_items_run_id",
        "provider_import_run_items",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_provider_import_run_items_run_id", table_name="provider_import_run_items")
    op.drop_table("provider_import_run_items")
    op.drop_index("ix_provider_import_runs_provider", table_name="provider_import_runs")
    op.drop_table("provider_import_runs")
    op.drop_index("ix_products_cod_product", table_name="products")
    op.drop_index("ix_products_provider", table_name="products")
    op.drop_column("products", "provider_source_url")
    op.drop_column("products", "provider")
