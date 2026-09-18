from abc import ABC, abstractmethod

from aiogram.types import Message as AiogramMessage
from companion_core import AnyMessage

from companion.bot.amc import AgentMessageComposerABC


class AgentMessageComposeView(ABC):
    @abstractmethod
    async def stream_view(
        self,
        role: str,
        message: AiogramMessage,
        amc: AgentMessageComposerABC,
    ) -> AnyMessage: ...
