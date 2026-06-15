"""opendata.programma_cache + opendata.comune_knowledge — cache analisi (F1).

Stub mirror della migrazione canonica del submodule agent-stack (non
materializzato in questo checkout). Vedi db/models.py::ProgrammaCache e
ComuneKnowledge.

Revision ID: 0004_programma_cache
Revises: 0003_comuni_anagrafica
Create Date: 2026-06-14
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_programma_cache"
down_revision: Union[str, None] = "0003_comuni_anagrafica"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS opendata")
    op.create_table(
        "comune_knowledge",
        sa.Column("cod_comune", sa.Text(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="opendata",
    )
    op.create_table(
        "programma_cache",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("cache_key", sa.Text(), nullable=False, unique=True),
        sa.Column("cod_comune", sa.Text(), nullable=False),
        sa.Column("tema", sa.Text(), nullable=True),
        sa.Column("modalita", sa.Text(), nullable=False),
        sa.Column("knowledge_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("scheda_json", sa.Text(), nullable=False),
        sa.Column("generato_il", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="opendata",
    )
    op.create_index(
        "ix_programma_cache_comune", "programma_cache", ["cod_comune"], schema="opendata"
    )


def downgrade() -> None:
    op.drop_index("ix_programma_cache_comune", table_name="programma_cache", schema="opendata")
    op.drop_table("programma_cache", schema="opendata")
    op.drop_table("comune_knowledge", schema="opendata")
