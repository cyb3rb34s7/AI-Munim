"""Standard response envelopes.

Per docs/conventions.md §4: every API response has the same outer shape with a
boolean `success` discriminator, so the frontend handles success vs error in
one place instead of in every component.

Success: { success: true, data: T, trace_id }
Error:   { success: false, error: { code, message, details? }, trace_id }
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessEnvelope(BaseModel, Generic[T]):
    success: bool = True
    data: T
    trace_id: str


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    success: bool = False
    error: ErrorPayload
    trace_id: str


def build_error_envelope(
    code: str,
    message: str,
    details: dict[str, Any] | None,
    trace_id: str,
) -> dict[str, Any]:
    return ErrorEnvelope(
        error=ErrorPayload(code=code, message=message, details=details),
        trace_id=trace_id,
    ).model_dump(mode="json")
