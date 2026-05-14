from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from munim.modules.chat.schemas import ChatMessageRequest, ChatMessageResponse
from munim.modules.chat.service import handle_chat_message
from munim.shared.db import DEFAULT_MERCHANT_ID, get_session
from munim.shared.responses import SuccessEnvelope

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/messages", response_model=SuccessEnvelope[ChatMessageResponse])
async def post_message(
    body: ChatMessageRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> SuccessEnvelope[ChatMessageResponse]:
    result = await handle_chat_message(
        session,
        DEFAULT_MERCHANT_ID,
        body.message,
        trace_id=request.state.trace_id,
    )
    session.commit()
    return SuccessEnvelope(data=result, trace_id=request.state.trace_id)
