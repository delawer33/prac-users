from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

if TYPE_CHECKING:
    from src.models.users import UserModel


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
    orders_count: int
    last_ordered_at: datetime | None
    total_spent: float


class UserResolveResponse(BaseModel):
    user: UserRead
    created: bool

    @classmethod
    def from_resolution(cls, user: UserModel, *, created_by_request: bool) -> UserResolveResponse:
        return cls(
            user=UserRead.model_validate(user),
            created=created_by_request,
        )
