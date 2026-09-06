import logging
from abc import ABC, abstractmethod
from collections import namedtuple
from collections.abc import AsyncGenerator, Iterable
from typing import Literal, TypeVar

from companion_core.types import AnyMessage

log = logging.getLogger(__name__)

OriginalMessage = TypeVar("OriginalMessage")
OriginalMessageData = namedtuple(
    "OriginalMessageData", ("original_message", "message_role")
)


class AgentMessageComposer[OriginalMessage](ABC):
    """The Agent message composer (AMC) interface."""

    @abstractmethod
    async def compose(
        self,
        message: OriginalMessage,
        role: Literal["assistant", "user"],
    ) -> AnyMessage: ...

    async def compose_conveyor(
        self, messages: Iterable[OriginalMessageData | AnyMessage]
    ) -> AsyncGenerator[AnyMessage]:
        for message in messages:
            if isinstance(message, tuple):
                yield await self.compose(message=message[0], role=message[1])
            else:
                yield message
