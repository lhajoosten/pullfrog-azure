from datetime import datetime

from pullfrog_azure_api.auth.domain import AuthErrorCode
from pydantic import BaseModel


class AuthErrorResponse(BaseModel):
    error: AuthErrorCode


class AdminSessionResponse(BaseModel):
    display_name: str | None
    idle_expires_at: datetime
    absolute_expires_at: datetime
