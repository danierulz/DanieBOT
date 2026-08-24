"""Site settings for the editable home promo bar."""

from alembic import op
import sqlalchemy as sa

revision = "20260823_0008"
down_revision = "20260621_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )
    settings = sa.table(
        "site_settings",
        sa.column("key", sa.String),
        sa.column("value", sa.Text),
    )
    op.bulk_insert(
        settings,
        [
            {
                "key": "promo_banner_text",
                "value": "Compra mínima $100.000 · Envío a todo el país",
            },
            {"key": "promo_banner_activo", "value": "1"},
        ],
    )


def downgrade() -> None:
    op.drop_table("site_settings")
