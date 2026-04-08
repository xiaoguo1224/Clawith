"""Add optional tenant SSO portal and OAuth redirect base URLs."""

import sqlalchemy as sa
from alembic import op

revision = "20260408_sso_urls"
down_revision = ("be48e94fa052", "d9cbd43b62e5")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("sso_portal_url", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("oauth_redirect_base_url", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "oauth_redirect_base_url")
    op.drop_column("tenants", "sso_portal_url")
