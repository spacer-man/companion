import logging
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Literal, NotRequired, TypedDict, TypeVar

from companion_core.types import AnyMessage

log = logging.getLogger(__name__)

OriginalMessage = TypeVar("OriginalMessage")
OriginalMessageData = namedtuple(
    "OriginalMessageData", ("original_message", "message_role")
)


class MessageComposedMetadata(TypedDict):
    transcribed: NotRequired[str | None]


class AgentMessageComposer[OriginalMessage](ABC):
    """The Agent message composer (AMC) interface."""

    @abstractmethod
    async def compose(
        self,
        message: OriginalMessage,
        role: Literal["assistant", "user"],
    ) -> tuple[AnyMessage, MessageComposedMetadata | None]: ...
