"""Add opendata.users BYOK columns — user's own LLM credential.

byok_provider ("claude"|"ollama_cloud"|NULL), byok_key_encrypted (Fernet
ciphertext of the API key, never plaintext) and byok_model (the chosen Ollama
Cloud model; NULL for claude). A user gets LLM access when a provider is set
here OR their subscription_tier is paid.

Revision ID: 0012_user_llm_keys
Revises: 0011_stripe_customer_id
Create Date: 2026-06-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_user_llm_keys"
down_revision: Union[str, None] = "0011_stripe_customer_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("byok_provider", sa.Text(), nullable=True), schema="opendata")
    op.add_column("users", sa.Column("byok_key_encrypted", sa.Text(), nullable=True), schema="opendata")
    op.add_column("users", sa.Column("byok_model", sa.Text(), nullable=True), schema="opendata")


def downgrade() -> None:
    op.drop_column("users", "byok_model", schema="opendata")
    op.drop_column("users", "byok_key_encrypted", schema="opendata")
    op.drop_column("users", "byok_provider", schema="opendata")
