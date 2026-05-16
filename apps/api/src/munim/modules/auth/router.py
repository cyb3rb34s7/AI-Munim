"""HTTP routes for /auth/*.

The signed session cookie carries `{merchant_id, user_id}`. Writes happen
inside `request.session[...] = ...`; SessionMiddleware serializes + signs +
sets the cookie on the response. Clearing the cookie is `request.session.clear()`
which the middleware translates into a delete-cookie response header.
"""

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from munim.models import User
from munim.modules.auth.dependencies import (
    SESSION_MERCHANT_KEY,
    SESSION_USER_KEY,
    get_current_merchant_id,
    get_current_user,
)
from munim.modules.auth.schemas import CurrentUser, StartDemoRequest
from munim.modules.auth.seed import seed_new_merchant
from munim.modules.auth.service import get_current_user_info, start_demo_session
from munim.shared.db import get_session
from munim.shared.responses import SuccessEnvelope

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/start", response_model=SuccessEnvelope[CurrentUser])
async def start_demo_endpoint(
    body: StartDemoRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> SuccessEnvelope[CurrentUser]:
    current_user = start_demo_session(session, body.display_name)
    await seed_new_merchant(session, current_user.merchant_id)
    session.commit()
    request.session[SESSION_MERCHANT_KEY] = current_user.merchant_id
    request.session[SESSION_USER_KEY] = current_user.user_id
    return SuccessEnvelope(data=current_user, trace_id=request.state.trace_id)


@router.get("/me", response_model=SuccessEnvelope[CurrentUser])
def me_endpoint(
    request: Request,
    merchant_id: str = Depends(get_current_merchant_id),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SuccessEnvelope[CurrentUser]:
    current = get_current_user_info(session, merchant_id, user.id)
    return SuccessEnvelope(data=current, trace_id=request.state.trace_id)


@router.post("/logout", response_model=SuccessEnvelope[dict[str, bool]])
def logout_endpoint(request: Request) -> SuccessEnvelope[dict[str, bool]]:
    request.session.clear()
    return SuccessEnvelope(data={"logged_out": True}, trace_id=request.state.trace_id)
