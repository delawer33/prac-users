from typing import Annotated

from fastapi import Depends

from src.db import SessionDep
from src.repositories.users import UsersRepository
from src.services.users import UsersService


def get_users_repository(session: SessionDep) -> UsersRepository:
    return UsersRepository(session)


def get_users_service(
    repository: Annotated[UsersRepository, Depends(get_users_repository)],
) -> UsersService:
    return UsersService(repository)


UsersRepositoryDep = Annotated[UsersRepository, Depends(get_users_repository)]
UsersServiceDep = Annotated[UsersService, Depends(get_users_service)]
