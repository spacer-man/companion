from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Literal

from aiogram.types import Message as AiogramMessage
from companion_core import AnyMessage

from .events import (
    MessageComposeEvent,
)


class AgentMessageComposerABC(ABC):
    """Abstract Agent Message Composer."""

    @abstractmethod
    def stream_compose(
        self,
        message: AiogramMessage,
        role: str,
    ) -> AsyncGenerator[MessageComposeEvent]: ...

    async def compose(
        self,
        message: AiogramMessage,
        role: Literal["assistant", "user"],
    ) -> AnyMessage:
        composed = None
        async for event in self.stream_compose(message=message, role=role):
            if event.data.type == "done":
                composed = event.data.message

        if not composed:
            raise RuntimeError("Failed compose message: %r", message)

        return composed
