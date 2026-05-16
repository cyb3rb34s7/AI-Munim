"""FastAPI dependencies that read the anonymous session cookie.

The session is mounted in main.py via starlette's SessionMiddleware (HMAC-signed
cookie carrying `{merchant_id, user_id}`). The dependencies here translate
"session missing or invalid" into a typed `UnauthenticatedError` so the global
error handler emits the standard envelope with code `auth.unauthenticated`.
"""

from fastapi import Depends, Request
from sqlmodel import Session

from munim.models import User
from munim.shared.constants import ErrorCode
from munim.shared.db import get_session as _get_session_dep
from munim.shared.errors import MunimError

_session_dep = Depends(_get_session_dep)

SESSION_MERCHANT_KEY = "merchant_id"
SESSION_USER_KEY = "user_id"


class UnauthenticatedError(MunimError):
    code = ErrorCode.AUTH_UNAUTHENTICATED.value
    http_status = 401
    message = "No active session. Start a demo session first."


async def get_current_merchant_id(request: Request) -> str:
    merchant_id = request.session.get(SESSION_MERCHANT_KEY)
    if not merchant_id or not isinstance(merchant_id, str):
        raise UnauthenticatedError()
    return merchant_id


async def get_current_user(
    request: Request,
    session: Session = _session_dep,
) -> User:
    user_id = request.session.get(SESSION_USER_KEY)
    if not user_id or not isinstance(user_id, str):
        raise UnauthenticatedError()
    user = session.get(User, user_id)
    if user is None:
        raise UnauthenticatedError(message="Session references an unknown user.")
    return user
