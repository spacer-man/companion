import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolCallError(Exception):
    pass


class Message(BaseModel):
    role: str = Field(frozen=True)
    content: str | None

    model_config = ConfigDict(extra="allow")


class UserMessage(Message):
    role: Literal["user"] = Field("user", init=False, frozen=True)
    images: list[str] | None = None
    """Images decoded to base64."""

    model_config = ConfigDict(extra="ignore")


class SystemMessage(Message):
    role: Literal["system"] = Field("system", init=False, frozen=True)

    model_config = ConfigDict(extra="ignore")


class AiMessage(Message):
    role: Literal["assistant"] = Field("assistant", init=False, frozen=True)
    images: list[str] | None = None
    reasoning: str | None = None
    tool_calls: list[ToolCall] | None = None

    model_config = ConfigDict(extra="ignore")


class ToolMessage(Message):
    role: Literal["tool"] = Field("tool", init=False, frozen=True)

    model_config = ConfigDict(extra="ignore")


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
