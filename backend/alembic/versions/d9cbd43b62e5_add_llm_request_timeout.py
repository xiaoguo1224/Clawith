"""add llm request_timeout

Revision ID: d9cbd43b62e5
Revises: 440261f5594f
Create Date: 2026-04-01 18:18:53.009382
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9cbd43b62e5'
down_revision: Union[str, None] = '440261f5594f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("llm_models")}
    if "request_timeout" not in columns:
        op.add_column("llm_models", sa.Column("request_timeout", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("llm_models")}
    if "request_timeout" in columns:
        op.drop_column("llm_models", "request_timeout")
