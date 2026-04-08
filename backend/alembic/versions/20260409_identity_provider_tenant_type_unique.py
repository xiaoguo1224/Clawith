"""Deduplicate feishu/wecom/dingtalk identity_providers per tenant; add partial unique index.

Generic OAuth2 (provider_type=oauth2) may still have multiple rows per tenant.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260409_idp_tenant_type_uq"
down_revision = "20260408_sso_urls"
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()

    rows = conn.execute(
        sa.text(
            """
            SELECT tenant_id, provider_type,
                   array_agg(id ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST) AS ids
            FROM identity_providers
            WHERE tenant_id IS NOT NULL
              AND provider_type IN ('feishu', 'dingtalk', 'wecom')
            GROUP BY tenant_id, provider_type
            HAVING COUNT(*) > 1
            """
        )
    )

    for tenant_id, provider_type, ids in rows:
        if not ids or len(ids) < 2:
            continue
        keeper = ids[0]
        for drop_id in ids[1:]:
            conn.execute(
                sa.text("UPDATE org_members SET provider_id = :k WHERE provider_id = :d"),
                {"k": str(keeper), "d": str(drop_id)},
            )
            conn.execute(
                sa.text("UPDATE org_departments SET provider_id = :k WHERE provider_id = :d"),
                {"k": str(keeper), "d": str(drop_id)},
            )
            conn.execute(
                sa.text("DELETE FROM identity_providers WHERE id = :d"),
                {"d": str(drop_id)},
            )

    op.create_index(
        "uq_identity_providers_tenant_feishu_wecom_dingtalk",
        "identity_providers",
        ["tenant_id", "provider_type"],
        unique=True,
        postgresql_where=sa.text(
            "tenant_id IS NOT NULL AND provider_type IN ('feishu', 'dingtalk', 'wecom')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_identity_providers_tenant_feishu_wecom_dingtalk",
        table_name="identity_providers",
    )
