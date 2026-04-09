"""Normalize empty-string email/phone/username on identities to NULL.

Duplicate '' violates UNIQUE on identities.email (PostgreSQL allows many NULLs).
"""

import sqlalchemy as sa
from alembic import op

revision = "20260410_blank_identity_null"
down_revision = "20260409_idp_tenant_type_uq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE identities SET email = NULL WHERE email = ''"))
    conn.execute(sa.text("UPDATE identities SET phone = NULL WHERE phone = ''"))
    conn.execute(sa.text("UPDATE identities SET username = NULL WHERE username = ''"))


def downgrade() -> None:
    pass
