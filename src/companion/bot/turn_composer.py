"""
User Turn composer.
"""

from abc import ABC, abstractmethod

from companion_core.types import Message


class TurnComposerABC(ABC):
    """Abstract User Turn composer."""

    @abstractmethod
    async def compose_turn(
        self,
        role: str,
        messages: list[Message],
    ) -> Message:
        """Compose user Turn from messages."""


class SimpleTurnComposer(TurnComposerABC):
    """Aiogram User Turn composer implementation."""

    async def compose_turn(
        self,
        role: str,
        messages: list[Message],
    ) -> Message:
        turn_content = "\n\n".join(m.content for m in messages if m.content)

        return Message(
            role=role,
            content=turn_content,
            images=[
                getattr(m, "images", None)
                for m in messages
                if getattr(m, "images", None)
            ],
        )
