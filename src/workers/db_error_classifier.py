from sqlalchemy.exc import (
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.exc import (
    TimeoutError as SQLTimeoutError,
)

# Коды ошибок Postgres, которые можно ретраить (infa / concurrency)
# https://www.postgresql.org/docs/current/errcodes-appendix.html
_TRANSIENT_PG_CODES: frozenset[str] = frozenset(
    {
        "40001",  # serialization_failure
        "40P01",  # deadlock_detected
        "08000",  # connection_exception
        "08003",  # connection_does_not_exist
        "08006",  # connection_failure
        "08001",  # sqlclient_unable_to_establish_sqlconnection
        "08004",  # sqlserver_rejected_establishment_of_sqlconnection
        "57P01",  # admin_shutdown
        "57014",  # query_canceled (timeout / admin cancel)
        "53300",  # too_many_connections
    }
)


def pgcode(exc: SQLAlchemyError) -> str | None:
    orig = getattr(exc, "orig", None)
    if orig is None:
        return None
    code = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    return str(code) if code else None


def is_transient(exc: SQLAlchemyError) -> bool:
    # Таймауты или сломанные подключения - ретраим
    if isinstance(exc, (InterfaceError, SQLTimeoutError)):
        return True
    if not isinstance(exc, OperationalError):
        return False
    code = pgcode(exc)
    if code is not None:
        # Ошибка временная - ретраим
        return code in _TRANSIENT_PG_CODES
    return True


def error_reason(exc: SQLAlchemyError) -> str:
    code = pgcode(exc)
    suffix = f" pgcode={code}" if code else ""
    return f"db_{type(exc).__name__}: {exc}{suffix}"
