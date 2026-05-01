from uuid import UUID

from fastapi import APIRouter, status

from src.db import SessionDep
from src.schemas.users import UserCreate, UserRead, UserResolveRequest, UserResolveResponse
from src.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: UUID, session: SessionDep) -> UserRead:
    return await users_service.get_user(session, user_id)


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, session: SessionDep) -> UserRead:
    return await users_service.create_user(session, data)


@router.post("/resolve", response_model=UserResolveResponse)
async def resolve_user(data: UserResolveRequest, session: SessionDep) -> UserResolveResponse:
    return await users_service.resolve_user(session, data)


@router.post("/{user_id}/saga-cancellation", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_user_for_order_saga(user_id: UUID, session: SessionDep) -> None:
    await users_service.cancel_user_for_order_saga(session, user_id)
