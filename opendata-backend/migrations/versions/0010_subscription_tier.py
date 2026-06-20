"""Add opendata.users.subscription_tier — access-control tier hook.

Every authenticated user gets a `subscription_tier` (default "free"). The
column is the data hook for API-key / A2A access limits; the concrete plans
and per-tier quotas are layered on later without further schema changes.

Revision ID: 0010_subscription_tier
Revises: 0009_civic_community
Create Date: 2026-06-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_subscription_tier"
down_revision: Union[str, None] = "0009_civic_community"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "subscription_tier",
            sa.Text(),
            nullable=False,
            server_default="free",
        ),
        schema="opendata",
    )


def downgrade() -> None:
    op.drop_column("users", "subscription_tier", schema="opendata")
