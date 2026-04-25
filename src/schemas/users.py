from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class UserResolveRequest(BaseModel):
    email: EmailStr
    external_request_id: str = Field(min_length=1, max_length=255)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str | None
    email: str
    first_name: str | None
    last_name: str | None
    is_active: bool
    created_at: datetime


class UserResolveResponse(BaseModel):
    user: UserRead
    created: bool
