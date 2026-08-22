from datetime import datetime
from uuid import UUID, uuid4

from pullfrog_azure_api.auth.domain import JsonValue
from pullfrog_azure_api.db.base import Base
from sqlalchemy import DateTime, Index, LargeBinary, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class OidcLoginAttempt(Base):
    __tablename__ = "oidc_login_attempt"
    __table_args__ = (
        UniqueConstraint(
            "token_digest",
            name="uq_oidc_login_attempt_token_digest",
        ),
        Index("ix_oidc_login_attempt_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    token_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    flow: Mapped[dict[str, JsonValue]] = mapped_column(JSONB, nullable=False)
    return_to: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
