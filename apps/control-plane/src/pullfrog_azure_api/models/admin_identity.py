from datetime import datetime
from uuid import UUID, uuid4

from pullfrog_azure_api.auth.domain import AdminIdentityKind
from pullfrog_azure_api.db.base import Base
from sqlalchemy import CheckConstraint, DateTime, Enum, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

ADMIN_IDENTITY_KIND_TYPE = Enum(
    AdminIdentityKind,
    native_enum=False,
    values_callable=lambda enum_class: [kind.value for kind in enum_class],
    create_constraint=False,
    length=5,
)


class AdminIdentity(Base):
    __tablename__ = "admin_identity"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('user', 'group')",
            name="ck_admin_identity_kind",
        ),
        UniqueConstraint(
            "tenant_id",
            "kind",
            "entra_object_id",
            name="uq_admin_identity_tenant_id_kind_entra_object_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[AdminIdentityKind] = mapped_column(ADMIN_IDENTITY_KIND_TYPE, nullable=False)
    entra_object_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
