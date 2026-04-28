"""Add agents.common_prompts for quick chat snippets."""

import sqlalchemy as sa
from alembic import op

revision = "add_agent_common_prompts"
down_revision = "20260415_pending_initial_setup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("agents")}
    if "common_prompts" not in cols:
        op.add_column(
            "agents",
            sa.Column(
                "common_prompts",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'::json"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("agents")}
    if "common_prompts" in cols:
        op.drop_column("agents", "common_prompts")
