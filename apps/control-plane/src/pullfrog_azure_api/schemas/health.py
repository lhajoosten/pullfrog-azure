from typing import Literal

from pullfrog_azure_api.services.readiness import ReadinessStatus
from pydantic import BaseModel


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: ReadinessStatus
