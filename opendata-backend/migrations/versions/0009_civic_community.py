"""opendata.civic_snapshots + community_* — sito civico e accountability (Fase 4).

Stub mirror della migrazione canonica (submodule agent-stack, non materializzato).
Snapshot pubblici NON sovrascritti: UNIQUE(istat_code, snapshot_id). JSONB/JSON per dialetto.

Revision ID: 0009_civic_community
Revises: 0008_raw_ingest
Create Date: 2026-06-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_civic_community"
down_revision: Union[str, None] = "0008_raw_ingest"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSONB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS opendata")

    op.create_table(
        "civic_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("istat_code", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("sources_version", sa.Text(), nullable=True),
        sa.Column("kpi_version", sa.Text(), nullable=True),
        sa.Column("payload_jsonb", _JSONB, nullable=True),
        sa.Column("kpi_jsonb", _JSONB, nullable=True),
        sa.UniqueConstraint("istat_code", "snapshot_id", name="uq_civic_snapshot"),
        schema="opendata",
    )
    op.create_index("ix_civic_snapshots_istat", "civic_snapshots", ["istat_code"], schema="opendata")

    op.create_table(
        "community_members",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("clerk_user_id", sa.Text(), nullable=False),
        sa.Column("istat_code", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="cittadino"),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("clerk_user_id", "istat_code", name="uq_community_member"),
        schema="opendata",
    )

    op.create_table(
        "community_threads",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("istat_code", sa.Text(), nullable=False),
        sa.Column("topic_type", sa.Text(), nullable=False),
        sa.Column("topic_ref", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="opendata",
    )
    op.create_index("ix_community_threads_istat", "community_threads", ["istat_code"], schema="opendata")

    op.create_table(
        "community_posts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("thread_id", sa.BigInteger(), nullable=False),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="visible"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["thread_id"], ["opendata.community_threads.id"],
                                name="fk_community_posts_thread", ondelete="CASCADE"),
        schema="opendata",
    )
    op.create_index("ix_community_posts_thread", "community_posts", ["thread_id"], schema="opendata")


def downgrade() -> None:
    op.drop_index("ix_community_posts_thread", table_name="community_posts", schema="opendata")
    op.drop_table("community_posts", schema="opendata")
    op.drop_index("ix_community_threads_istat", table_name="community_threads", schema="opendata")
    op.drop_table("community_threads", schema="opendata")
    op.drop_table("community_members", schema="opendata")
    op.drop_index("ix_civic_snapshots_istat", table_name="civic_snapshots", schema="opendata")
    op.drop_table("civic_snapshots", schema="opendata")
