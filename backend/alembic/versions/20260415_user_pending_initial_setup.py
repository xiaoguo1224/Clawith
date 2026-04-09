"""Add users.pending_initial_setup for passwordless new-account wizard."""

import sqlalchemy as sa
from alembic import op

revision = "20260415_pending_initial_setup"
down_revision = "20260410_blank_identity_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "pending_initial_setup",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # New rows default false at DB level; ORM sets true in code when identity has no password.
    op.alter_column("users", "pending_initial_setup", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "pending_initial_setup")
