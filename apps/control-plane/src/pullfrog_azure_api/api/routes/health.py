from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pullfrog_azure_api.api.dependencies import get_readiness_service
from pullfrog_azure_api.schemas.health import LivenessResponse, ReadinessResponse
from pullfrog_azure_api.services.readiness import ReadinessService, ReadinessStatus

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
async def readiness(
    service: Annotated[ReadinessService, Depends(get_readiness_service)],
) -> JSONResponse:
    status = await service.check()
    status_code = 200 if status is ReadinessStatus.READY else 503
    payload = ReadinessResponse(status=status).model_dump(mode="json")
    return JSONResponse(status_code=status_code, content=payload)
