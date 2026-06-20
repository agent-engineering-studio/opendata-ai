"""Add opendata.users.stripe_customer_id — bind Stripe customer to user.

Set on checkout.session.completed so later customer.subscription.* events
(keyed only by the Stripe customer id) can map back to the local user and
update subscription_tier. Indexed for the by-customer lookup.

Revision ID: 0011_stripe_customer_id
Revises: 0010_subscription_tier
Create Date: 2026-06-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_stripe_customer_id"
down_revision: Union[str, None] = "0010_subscription_tier"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("stripe_customer_id", sa.Text(), nullable=True),
        schema="opendata",
    )
    op.create_index(
        "ix_users_stripe_customer_id",
        "users",
        ["stripe_customer_id"],
        schema="opendata",
    )


def downgrade() -> None:
    op.drop_index("ix_users_stripe_customer_id", table_name="users", schema="opendata")
    op.drop_column("users", "stripe_customer_id", schema="opendata")
