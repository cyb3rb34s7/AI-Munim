"""Chat service. Thin wrapper around `chat.agent.answer_question`."""

from sqlmodel import Session

from munim.chat.agent import answer_question
from munim.chat.tools import ChatContext
from munim.modules.chat.schemas import ChatMessageResponse


async def handle_chat_message(
    session: Session,
    merchant_id: str,
    message: str,
    *,
    trace_id: str | None = None,
) -> ChatMessageResponse:
    ctx = ChatContext(merchant_id=merchant_id, session=session, trace_id=trace_id)
    answered = await answer_question(question=message, ctx=ctx)
    return ChatMessageResponse(text=answered.text, citations=answered.citations)
