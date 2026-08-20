from datetime import datetime
from uuid import UUID, uuid4

from pullfrog_azure_api.db.base import Base
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column


class DeploymentSettings(Base):
    __tablename__ = "deployment_settings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entra_tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
