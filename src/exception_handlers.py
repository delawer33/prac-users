import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from src.exceptions import UserDeletionForbiddenError, UserEmailAlreadyExistsError, UserNotFoundError
from src.request_context import request_id_var

logger = logging.getLogger(__name__)


def _error_content(
    request: Request,
    details: Any,
) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", None) or request_id_var.get() or ""
    return {"request_id": request_id, "details": details}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(
        request: Request,
        exc: SQLAlchemyError,
    ) -> JSONResponse:
        logger.exception(
            "sqlalchemy error method=%s path=%s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_content(
                request,
                "Database error",
            ),
        )

    @app.exception_handler(UserNotFoundError)
    async def user_not_found_handler(
        request: Request,
        exc: UserNotFoundError,
    ) -> JSONResponse:
        logger.warning("user not found user_id=%s", exc.user_id)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_error_content(
                request,
                "User not found",
            ),
        )

    @app.exception_handler(UserEmailAlreadyExistsError)
    async def user_email_already_exists_handler(
        request: Request,
        exc: UserEmailAlreadyExistsError,
    ) -> JSONResponse:
        logger.warning("email already registered email=%s", exc.email)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_content(
                request,
                "Email already registered",
            ),
        )

    @app.exception_handler(UserDeletionForbiddenError)
    async def user_deletion_forbidden_handler(
        request: Request,
        exc: UserDeletionForbiddenError,
    ) -> JSONResponse:
        logger.warning("user deletion forbidden user_id=%s", exc.user_id)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_content(
                request,
                "Active user cannot be deleted",
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_content(
                request,
                exc.errors(),
            ),
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_handler(
        request: Request,
        exc: ValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_content(
                request,
                exc.errors(),
            ),
        )
