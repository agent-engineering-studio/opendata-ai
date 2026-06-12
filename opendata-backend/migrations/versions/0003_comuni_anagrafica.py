"""opendata.comuni_anagrafica — anagrafica comuni per il peer group (spec 08).

Stub mirror della migrazione canonica che appartiene al submodule agent-stack
(non materializzato in questo checkout — aggiungere lì il gemello quando lo
sarà). Vedi db/models.py::ComuneAnagrafica.

Revision ID: 0003_comuni_anagrafica
Revises: 0002_oc_progetti
Create Date: 2026-06-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_comuni_anagrafica"
down_revision: Union[str, None] = "0002_oc_progetti"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS opendata")
    op.create_table(
        "comuni_anagrafica",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("cod_comune", sa.Text(), nullable=False, unique=True),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("cod_provincia", sa.Text(), nullable=True),
        sa.Column("cod_regione", sa.Text(), nullable=True),
        sa.Column("popolazione", sa.Integer(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="opendata",
    )
    op.create_index(
        "ix_comuni_anagrafica_regione", "comuni_anagrafica", ["cod_regione"], schema="opendata"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_comuni_anagrafica_regione", table_name="comuni_anagrafica", schema="opendata"
    )
    op.drop_table("comuni_anagrafica", schema="opendata")
