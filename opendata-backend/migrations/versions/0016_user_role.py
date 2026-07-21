"""Add opendata.users.role — RBAC authorization hook (#235).

Authentication is delegated to the OIDC IdP (Keycloak — SPID / email-OTP
registration); the *role* that drives authorization lives here and is managed
by an admin from the admin dashboard. Every user gets a role, default
"cittadino"; "admin" can manage other users' roles.

Revision ID: 0016_user_role
Revises: 0015_dataplan_plans
Create Date: 2026-07-21
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_user_role"
down_revision: Union[str, None] = "0015_dataplan_plans"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.Text(), nullable=False, server_default="cittadino"),
        schema="opendata",
    )


def downgrade() -> None:
    op.drop_column("users", "role", schema="opendata")
