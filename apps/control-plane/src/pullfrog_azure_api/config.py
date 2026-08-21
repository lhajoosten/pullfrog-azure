from typing import Annotated, Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import AnyHttpUrl, Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PULLFROG_", extra="ignore")

    database_url: PostgresDsn


class Settings(DatabaseSettings):
    app_name: str = "Pullfrog Azure"
    app_version: str = "0.1.0"
    readiness_timeout_seconds: float = Field(default=3.0, gt=0)
    entra_tenant_id: UUID
    entra_client_id: UUID
    entra_client_secret: SecretStr
    public_base_url: AnyHttpUrl
    admin_user_object_ids: Annotated[tuple[UUID, ...], NoDecode] = ()
    admin_group_object_ids: Annotated[tuple[UUID, ...], NoDecode] = ()
    admin_session_idle_minutes: int = Field(default=30, ge=10, le=1_440)
    admin_session_absolute_hours: int = Field(default=8, ge=1, le=168)
    oidc_login_attempt_minutes: int = Field(default=10, ge=1, le=10)
    allow_insecure_local_cookies: bool = False
    oidc_http_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    oidc_operation_timeout_seconds: float = Field(default=10.0, gt=0, le=60)

    @field_validator("admin_user_object_ids", "admin_group_object_ids", mode="before")
    @classmethod
    def parse_identity_ids(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if not value:
            return ()

        values = tuple(entry.strip() for entry in value.split(","))
        if not values or any(not entry for entry in values):
            raise ValueError("administrator object ID lists must not contain empty entries")
        return values

    @field_validator("admin_user_object_ids", "admin_group_object_ids")
    @classmethod
    def reject_duplicate_identity_ids(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if len(value) != len(set(value)):
            raise ValueError("administrator object ID lists must not contain duplicates")
        return value

    @field_validator("public_base_url")
    @classmethod
    def require_origin_only_public_base_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        parsed = urlsplit(str(value))
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("public base URL must not include credentials")
        if value.query is not None or value.fragment is not None:
            raise ValueError("public base URL must not include a query or fragment")
        if parsed.path not in ("", "/"):
            raise ValueError("public base URL must be an origin")
        return value

    @model_validator(mode="after")
    def validate_deployment_security(self) -> Self:
        public_base_url = urlsplit(str(self.public_base_url))
        is_loopback = public_base_url.hostname in {"localhost", "127.0.0.1", "::1"}

        if public_base_url.scheme == "http":
            if not self.allow_insecure_local_cookies or not is_loopback:
                raise ValueError("HTTP public base URLs require explicit loopback development mode")
        elif self.allow_insecure_local_cookies:
            raise ValueError("insecure local cookies require a loopback HTTP public base URL")

        if not self.admin_user_object_ids and not self.admin_group_object_ids:
            raise ValueError("at least one bootstrap administrator object ID is required")

        if self.admin_session_absolute_hours * 60 <= self.admin_session_idle_minutes:
            raise ValueError("absolute session expiry must exceed idle session expiry")

        return self

    @property
    def secure_cookies(self) -> bool:
        return not self.allow_insecure_local_cookies

    @property
    def callback_url(self) -> str:
        return f"{str(self.public_base_url).rstrip('/')}/api/v1/auth/callback"
