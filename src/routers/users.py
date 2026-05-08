from uuid import UUID

from fastapi import APIRouter, status

from .dependencies import UsersServiceDep
from src.schemas.users import UserCreate, UserRead, UserResolveRequest, UserResolveResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: UUID, service: UsersServiceDep) -> UserRead:
    return await service.get_user(user_id)


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, service: UsersServiceDep) -> UserRead:
    return await service.create_user(data)


@router.post("/resolve", response_model=UserResolveResponse)
async def resolve_user(data: UserResolveRequest, service: UsersServiceDep) -> UserResolveResponse:
    return await service.resolve_user(data)


@router.post("/{user_id}/saga-cancellation", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_user_for_order_saga(user_id: UUID, service: UsersServiceDep) -> None:
    await service.cancel_user_for_order_saga(user_id)
