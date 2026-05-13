"""Structured JSON logging.

Every log line is one JSON object on stdout with these guaranteed fields:
    event, level, timestamp, trace_id (when inside a request),
    plus any kwargs passed at the call site.

trace_id is propagated automatically via structlog contextvars (bound by
TraceIdMiddleware in `trace.py`), so callers never have to thread it through
function arguments.

Per docs/conventions.md §5.3: no `print()`, no stdlib `logging.info` calls.
Always use `get_logger(...)`.
"""

import logging
import sys
from typing import cast

import structlog

from munim.shared.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    # structlog.get_logger returns a lazy proxy typed as Any; cast at the seam.
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
