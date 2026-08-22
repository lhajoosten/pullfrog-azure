from datetime import datetime
from uuid import UUID, uuid4

from pullfrog_azure_api.auth.domain import AdminIdentityKind
from pullfrog_azure_api.db.base import Base
from pullfrog_azure_api.models.admin_identity import ADMIN_IDENTITY_KIND_TYPE
from sqlalchemy import CheckConstraint, DateTime, LargeBinary, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column


class AdminSession(Base):
    __tablename__ = "admin_session"
    __table_args__ = (
        CheckConstraint(
            "authorizing_kind IN ('user', 'group')",
            name="ck_admin_session_authorizing_kind",
        ),
        UniqueConstraint("token_digest", name="uq_admin_session_token_digest"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    token_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    csrf_token_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    user_object_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    authorizing_kind: Mapped[AdminIdentityKind] = mapped_column(
        ADMIN_IDENTITY_KIND_TYPE,
        nullable=False,
    )
    authorizing_object_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
