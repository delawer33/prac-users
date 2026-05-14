from enum import StrEnum

from pydantic import BaseModel


class HealthStatus(StrEnum):
    OK = "ok"


class HealthCheckResponse(BaseModel):
    status: HealthStatus
