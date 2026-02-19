"""Logging configuration for the application."""

from __future__ import annotations

import contextvars
import logging

from app.config import settings

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)


class RequestIdFilter(logging.Filter):
    """Attach request_id from contextvars to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get() or "-"
        else:
            record.request_id = record.request_id or request_id_var.get() or "-"
        return True


def configure_logging() -> None:
    """Configure structured logging for the service."""
    factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = factory(*args, **kwargs)
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get() or "-"
        return record

    logging.setLogRecordFactory(record_factory)
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s request_id=%(request_id)s",
    )
    root_logger = logging.getLogger()
    root_logger.addFilter(RequestIdFilter())
    for handler in root_logger.handlers:
        handler.addFilter(RequestIdFilter())
