"""Auth service. Creates the Merchant + User pair and looks up the current user.

Per docs/architecture.md §10: every visitor gets a fresh `Merchant` row. The
session cookie carries the `merchant_id` + `user_id`. The router writes the
cookie via `request.session[...]`; this service does no cookie work — it just
materialises the rows.
"""

from sqlmodel import Session
from ulid import ULID

from munim.models import Merchant, User
from munim.modules.auth.dependencies import UnauthenticatedError
from munim.modules.auth.schemas import CurrentUser

DEFAULT_DISPLAY_NAME = "Demo User"


def start_demo_session(session: Session, display_name: str | None) -> CurrentUser:
    """Create a new Merchant + User pair. Returns the materialised view."""
    merchant_id = f"m_{ULID()}"
    user_id = f"u_{ULID()}"
    resolved_name = (display_name or "").strip() or DEFAULT_DISPLAY_NAME
    merchant = Merchant(id=merchant_id, name=resolved_name)
    user = User(id=user_id, merchant_id=merchant_id, display_name=resolved_name)
    session.add(merchant)
    session.add(user)
    session.flush()
    return CurrentUser(
        merchant_id=merchant_id,
        user_id=user_id,
        display_name=resolved_name,
        created_at=user.created_at,
    )


def get_current_user_info(session: Session, merchant_id: str, user_id: str) -> CurrentUser:
    user = session.get(User, user_id)
    if user is None or user.merchant_id != merchant_id:
        raise UnauthenticatedError(message="Session references an unknown user.")
    return CurrentUser(
        merchant_id=user.merchant_id,
        user_id=user.id,
        display_name=user.display_name,
        created_at=user.created_at,
    )
