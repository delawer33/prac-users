from fastapi import APIRouter

from src.schemas.healthcheck import HealthCheckResponse

router = APIRouter()


@router.get('/healthcheck', response_model=HealthCheckResponse)
async def healthcheck() -> HealthCheckResponse:
    return HealthCheckResponse(status='ok')
