import json
from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCallError(Exception):
    pass


class Message(BaseModel):
    role: str = Field(init=False)
    content: str | None


class UserMessage(Message):
    role: str = "user"
    images: list[str] | None = None
    """Images decoded to base64."""


class SystemMessage(Message):
    role: str = "system"


class AiMessage(Message):
    role: str = "assistant"
    reasoning: str | None = None
    tool_calls: list[ToolCall] | None = None


class ToolMessage(Message):
    role: str = "tool"


class ToolFunction(BaseModel):
    name: str
    arguments: str

    def parsed_arguments(self) -> dict[str, Any]:
        return json.loads(self.arguments)


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolFunction


type AnyMessage = Message | AiMessage | UserMessage | ToolMessage


class Completion[MT: AnyMessage](BaseModel):
    message: MT
    finish_reason: (
        Literal["stop", "length", "tool_calls", "content_filter", "function_call"]
        | None
    ) = None
    current_chunk: str | None = None
