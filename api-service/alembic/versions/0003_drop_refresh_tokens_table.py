"""drop refresh_tokens table (moved to Redis)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-27
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS refresh_tokens;"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id         SERIAL PRIMARY KEY,
            token      VARCHAR(128) NOT NULL,
            user_id    INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TIMESTAMPTZ  NOT NULL,
            created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
        );
    """))
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_refresh_tokens_token   ON refresh_tokens (token);"))
    conn.execute(sa.text("CREATE        INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id);"))
