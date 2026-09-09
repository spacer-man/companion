from abc import ABC, abstractmethod
from collections import defaultdict

from companion_core.types import Message


class MessageStorageABC(ABC):
    """Abstract message storage."""

    @abstractmethod
    async def store(self, message: Message, session_id: str) -> None:
        """Store message to process it later."""

    @abstractmethod
    async def count(self, session_id: str) -> int:
        """Get stored messages count."""

    @abstractmethod
    async def pop(self, session_id: str) -> list[Message]:
        """Store message to process it later."""


class InmemoryMessageStorage(MessageStorageABC):
    """In memory message storage."""

    def __init__(self) -> None:
        self._data: dict[str, list[Message]] = defaultdict(list)

    async def store(self, message: Message, session_id: str) -> None:
        self._data[session_id].append(message)

    async def count(self, session_id: str) -> int:
        return len(self._data[session_id])

    async def pop(self, session_id: str) -> list[Message]:
        return self._data.pop(session_id)
