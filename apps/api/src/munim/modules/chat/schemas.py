from pydantic import BaseModel, ConfigDict, Field

from munim.chat.types import RowCitation


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    citations: list[RowCitation]
