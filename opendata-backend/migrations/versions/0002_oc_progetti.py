"""opendata.oc_progetti — local mirror of the OpenCoesione bulk dataset.

Stub mirror of the canonical migration that belongs in the agent-stack
submodule (`vendor/agent-stack/db/migrations/opendata/`). The submodule is
not materialised in this checkout — when it is, add the canonical twin there
and keep this stub in sync (same table, same columns, same constraints).

One row per (project CLP, comune): the bulk tracciato has a MULTI-VALUED
COD_COMUNE (':::'-joined), exploded at ingest. See db/models.py::OcProgetto.

Revision ID: 0002_oc_progetti
Revises: 0001_initial
Create Date: 2026-06-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_oc_progetti"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS opendata")

    op.create_table(
        "oc_progetti",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("clp", sa.Text(), nullable=False),
        sa.Column("cod_comune", sa.Text(), nullable=False, server_default=""),
        sa.Column("cod_provincia", sa.Text(), nullable=True),
        sa.Column("cod_regione", sa.Text(), nullable=True),
        sa.Column("tema", sa.Text(), nullable=True),
        sa.Column("ciclo", sa.Text(), nullable=True),
        sa.Column("natura", sa.Text(), nullable=True),
        sa.Column("stato", sa.Text(), nullable=True),
        sa.Column("finanziamento_totale", sa.Numeric(18, 2), nullable=True),
        sa.Column("pagamenti", sa.Numeric(18, 2), nullable=True),
        sa.Column("titolo", sa.Text(), nullable=True),
        sa.Column("soggetto_attuatore", sa.Text(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("clp", "cod_comune", name="uq_oc_progetti_clp_comune"),
        schema="opendata",
    )
    op.create_index(
        "ix_oc_progetti_comune_tema_ciclo",
        "oc_progetti",
        ["cod_comune", "tema", "ciclo"],
        schema="opendata",
    )
    op.create_index(
        "ix_oc_progetti_provincia", "oc_progetti", ["cod_provincia"], schema="opendata"
    )
    op.create_index(
        "ix_oc_progetti_regione", "oc_progetti", ["cod_regione"], schema="opendata"
    )


def downgrade() -> None:
    op.drop_index("ix_oc_progetti_regione", table_name="oc_progetti", schema="opendata")
    op.drop_index("ix_oc_progetti_provincia", table_name="oc_progetti", schema="opendata")
    op.drop_index("ix_oc_progetti_comune_tema_ciclo", table_name="oc_progetti", schema="opendata")
    op.drop_table("oc_progetti", schema="opendata")
