"""monitor_targets.kind + url nullable — watch di maturità (#103).

Un avviso di maturità È un monitor target (`kind='maturity'`, `entity_id`
obbligatorio a livello applicativo, nessun URL da scaricare): riusa webhook/
email, `monitor_runs` append-only e il no-renotify di `diff_runs`. I target
esistenti restano `kind='dataset'`.

Revision ID: 0014_monitor_maturity
Revises: 0013_monitor
Create Date: 2026-07-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_monitor_maturity"
down_revision: Union[str, None] = "0013_monitor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "monitor_targets",
        sa.Column("kind", sa.Text(), nullable=False, server_default=sa.text("'dataset'")),
        schema="opendata",
    )
    op.alter_column(
        "monitor_targets", "url",
        existing_type=sa.Text(), nullable=True,
        schema="opendata",
    )


def downgrade() -> None:
    # i watch di maturità non hanno URL: vanno rimossi prima di ripristinare il NOT NULL
    op.execute("DELETE FROM opendata.monitor_targets WHERE kind <> 'dataset'")
    op.alter_column(
        "monitor_targets", "url",
        existing_type=sa.Text(), nullable=False,
        schema="opendata",
    )
    op.drop_column("monitor_targets", "kind", schema="opendata")
