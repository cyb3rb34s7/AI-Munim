"""Trace ID generation, propagation, and the FastAPI middleware that binds it.

Per docs/conventions.md §5: every request gets a trace_id of shape
`tr_<26-char ULID>`. It is:
  - returned in the response envelope (via `request.state.trace_id`)
  - echoed in the `X-Trace-Id` response header
  - bound to structlog contextvars so every log line in the request emits it
  - honoured if the client passes a valid `X-Trace-Id` header on inbound
    (lets the frontend stitch retries to the original trace)
"""

from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from ulid import ULID

TRACE_ID_HEADER = "X-Trace-Id"
TRACE_ID_PREFIX = "tr_"
ULID_LEN = 26


def new_trace_id() -> str:
    return f"{TRACE_ID_PREFIX}{ULID()}"


def is_valid_trace_id(value: str) -> bool:
    return value.startswith(TRACE_ID_PREFIX) and len(value) == len(TRACE_ID_PREFIX) + ULID_LEN


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(TRACE_ID_HEADER, "")
        trace_id = incoming if is_valid_trace_id(incoming) else new_trace_id()

        request.state.trace_id = trace_id
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("trace_id")
        response.headers[TRACE_ID_HEADER] = trace_id
        return response
