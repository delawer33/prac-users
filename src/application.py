import logging

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.exceptions.exception_handlers import register_exception_handlers
from src.logging_filters import RequestIdLogFilter
from src.middleware.request_id import register_request_id_middleware
from src.routers.healthcheck import router as healthcheck_router
from src.routers.users import router as users_router

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s %(name)s "
            "[request_id=%(request_id)s] %(message)s"
        ),
    )
    request_id_filter = RequestIdLogFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(request_id_filter)


_configure_logging()

def get_app() -> FastAPI:
    """
    Get FastAPI application.

    This is the main constructor of an application.

    :return: application.
    """
    app = FastAPI(
        docs_url='/docs',
        openapi_url='/openapi.json',
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    register_request_id_middleware(app=app)

    register_exception_handlers(app)

    app.include_router(healthcheck_router)
    app.include_router(users_router, prefix="/v1")

    return app