"""opendata.documenti — registro documenti PA ingeriti nel KG (F2).

Stub mirror della migrazione canonica del submodule agent-stack (non
materializzato in questo checkout). Vedi db/models.py::Documento.

Revision ID: 0005_documenti
Revises: 0004_programma_cache
Create Date: 2026-06-14
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_documenti"
down_revision: Union[str, None] = "0004_programma_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS opendata")
    op.create_table(
        "documenti",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("cod_comune", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("kg_namespace", sa.Text(), nullable=False),
        sa.Column("kg_document_id", sa.Text(), nullable=True),
        sa.Column("pagine", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("stato", sa.Text(), nullable=False, server_default="in_ingest"),
        sa.Column("errore", sa.Text(), nullable=True),
        sa.Column("caricato_da", sa.Text(), nullable=True),
        sa.Column(
            "caricato_il",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="opendata",
    )
    op.create_index("ix_documenti_comune", "documenti", ["cod_comune"], schema="opendata")


def downgrade() -> None:
    op.drop_index("ix_documenti_comune", table_name="documenti", schema="opendata")
    op.drop_table("documenti", schema="opendata")
