"""initial: users and prediction_logs

Revision ID: 0001
Revises:
Create Date: 2026-06-27
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. ENUM — создаём только если не существует
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE role AS ENUM ('user', 'analyst', 'admin');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))

    # 2. Таблица users — CREATE TABLE IF NOT EXISTS
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS users (
            id               SERIAL PRIMARY KEY,
            email            VARCHAR(255) NOT NULL,
            hashed_password  VARCHAR(255) NOT NULL,
            role             role         NOT NULL DEFAULT 'user',
            is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
        );
    """))
    conn.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);
    """))

    # 3. Таблица prediction_logs — CREATE TABLE IF NOT EXISTS
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS prediction_logs (
            id            SERIAL PRIMARY KEY,
            user_id       INTEGER     NOT NULL REFERENCES users(id),
            request_data  JSONB       NOT NULL,
            response_data JSONB       NOT NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_prediction_logs_user_id ON prediction_logs (user_id);
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS prediction_logs;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS users;"))
    conn.execute(sa.text("DROP TYPE IF EXISTS role;"))
