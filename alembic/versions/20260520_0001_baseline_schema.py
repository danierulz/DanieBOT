"""baseline schema — esquema completo según modelos actuales

Revision ID: 20260520_0001
Revises:
Create Date: 2026-05-20

Para bases de datos en producción que ya tienen este esquema aplicado manualmente:
  python -m alembic stamp 20260520_0001

Para bases nuevas (vacías):
  python -m alembic upgrade head
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260520_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("category_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("category_id"),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)

    op.create_table(
        "sizes",
        sa.Column("size_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("size_id"),
    )
    op.create_index("ix_sizes_code", "sizes", ["code"], unique=True)

    op.create_table(
        "customers",
        sa.Column("customer_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wa_id", sa.String(length=32), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "marketing_email_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("marketing_email_consent_at", sa.DateTime(), nullable=True),
        sa.Column(
            "marketing_whatsapp_consent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("customer_id"),
    )
    op.create_index("ix_customers_wa_id", "customers", ["wa_id"], unique=True)

    op.create_table(
        "home_banners",
        sa.Column("banner_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("image_url", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=16), nullable=False, server_default="image"),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("subtitle", sa.String(length=300), nullable=True),
        sa.Column("link_href", sa.String(length=512), nullable=False, server_default="/"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("banner_id"),
    )

    op.create_table(
        "products",
        sa.Column("product_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("status", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("cod_product", sa.String(length=50), nullable=True),
        sa.Column("item_title", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=True),
        sa.Column("sku", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("is_sale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("discount_percent", sa.Integer(), nullable=True),
        sa.Column("extract_date", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("create_date", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["categories.category_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("product_id"),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"], unique=False)

    op.create_table(
        "orders",
        sa.Column("order_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_code", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pendiente"),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("customer_name", sa.String(length=200), nullable=True),
        sa.Column("customer_phone", sa.String(length=50), nullable=True),
        sa.Column("whatsapp_wa_id", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="web"),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="wa_me"),
        sa.Column("total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("cart_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.PrimaryKeyConstraint("order_id"),
    )
    op.create_index("ix_orders_order_code", "orders", ["order_code"], unique=True)
    op.create_index("ix_orders_order_id", "orders", ["order_id"], unique=False)
    op.create_index("ix_orders_whatsapp_wa_id", "orders", ["whatsapp_wa_id"], unique=False)
    op.create_index("ix_orders_status_created", "orders", ["status", "created_at"], unique=False)

    op.create_table(
        "product_images",
        sa.Column("image_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("is_main", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("image_id"),
    )

    op.create_table(
        "product_variants",
        sa.Column("variant_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("size_id", sa.Integer(), nullable=False),
        sa.Column("qty_stock_local", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("encargo_habilitado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("dias_encargo_estimados", sa.Integer(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["size_id"], ["sizes.size_id"]),
        sa.PrimaryKeyConstraint("variant_id"),
        sa.UniqueConstraint("product_id", "size_id", name="uq_product_variants_product_size"),
    )
    op.create_index("ix_product_variants_product_id", "product_variants", ["product_id"], unique=False)
    op.create_index("ix_product_variants_size_id", "product_variants", ["size_id"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("order_item_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("title_snapshot", sa.String(length=255), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("subtotal", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.order_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.variant_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("order_item_id"),
    )

    op.create_table(
        "order_events",
        sa.Column("event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.order_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_order_events_order_id", "order_events", ["order_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_order_events_order_id", table_name="order_events")
    op.drop_table("order_events")
    op.drop_table("order_items")
    op.drop_index("ix_product_variants_size_id", table_name="product_variants")
    op.drop_index("ix_product_variants_product_id", table_name="product_variants")
    op.drop_table("product_variants")
    op.drop_table("product_images")
    op.drop_index("ix_orders_status_created", table_name="orders")
    op.drop_index("ix_orders_whatsapp_wa_id", table_name="orders")
    op.drop_index("ix_orders_order_id", table_name="orders")
    op.drop_index("ix_orders_order_code", table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_table("products")
    op.drop_table("home_banners")
    op.drop_index("ix_customers_wa_id", table_name="customers")
    op.drop_table("customers")
    op.drop_index("ix_sizes_code", table_name="sizes")
    op.drop_table("sizes")
    op.drop_index("ix_categories_slug", table_name="categories")
    op.drop_table("categories")
