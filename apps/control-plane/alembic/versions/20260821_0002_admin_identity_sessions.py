"""Create admin identity and session schema.

Revision ID: 20260821_0002
Revises: 20260809_0001
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260821_0002"
down_revision: str | Sequence[str] | None = "20260809_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_identity",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "user",
                "group",
                native_enum=False,
                create_constraint=False,
                length=5,
            ),
            nullable=False,
        ),
        sa.Column("entra_object_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('user', 'group')", name="ck_admin_identity_kind"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "kind",
            "entra_object_id",
            name="uq_admin_identity_tenant_id_kind_entra_object_id",
        ),
    )
    op.create_table(
        "oidc_login_attempt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("flow", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("return_to", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest", name="uq_oidc_login_attempt_token_digest"),
    )
    op.create_index(
        "ix_oidc_login_attempt_expires_at",
        "oidc_login_attempt",
        ["expires_at"],
        unique=False,
    )
    op.create_table(
        "admin_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("csrf_token_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_object_id", sa.Uuid(), nullable=False),
        sa.Column(
            "authorizing_kind",
            sa.Enum(
                "user",
                "group",
                native_enum=False,
                create_constraint=False,
                length=5,
            ),
            nullable=False,
        ),
        sa.Column("authorizing_object_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "authorizing_kind IN ('user', 'group')",
            name="ck_admin_session_authorizing_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest", name="uq_admin_session_token_digest"),
    )


def downgrade() -> None:
    op.drop_table("admin_session")
    op.drop_index("ix_oidc_login_attempt_expires_at", table_name="oidc_login_attempt")
    op.drop_table("oidc_login_attempt")
    op.drop_table("admin_identity")
