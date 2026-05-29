"""product colors catalog and order line snapshots

Revision ID: 20260528_0002
Revises: 20260520_0001
Create Date: 2026-05-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0002"
down_revision: Union[str, None] = "20260520_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "colors",
        sa.Column("color_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hex", sa.String(length=7), nullable=True),
        sa.PrimaryKeyConstraint("color_id"),
    )
    op.create_index("ix_colors_code", "colors", ["code"], unique=True)

    op.create_table(
        "product_colors",
        sa.Column("product_color_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("color_id", sa.Integer(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["color_id"], ["colors.color_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("product_color_id"),
        sa.UniqueConstraint("product_id", "color_id", name="uq_product_colors_product_color"),
    )
    op.create_index("ix_product_colors_product_id", "product_colors", ["product_id"])
    op.create_index("ix_product_colors_color_id", "product_colors", ["color_id"])

    op.add_column("order_items", sa.Column("color_id", sa.Integer(), nullable=True))
    op.add_column(
        "order_items", sa.Column("size_label_snapshot", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "order_items", sa.Column("color_label_snapshot", sa.String(length=64), nullable=True)
    )
    op.create_foreign_key(
        "fk_order_items_color_id",
        "order_items",
        "colors",
        ["color_id"],
        ["color_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_order_items_color_id", "order_items", type_="foreignkey")
    op.drop_column("order_items", "color_label_snapshot")
    op.drop_column("order_items", "size_label_snapshot")
    op.drop_column("order_items", "color_id")
    op.drop_table("product_colors")
    op.drop_table("colors")
