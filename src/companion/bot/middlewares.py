import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

DEFAULT_NEW_MESSAGE_TIMEOUT = 5


class UpdateAccumulatorMiddleware(BaseMiddleware):
    """
    Simple update accumulator middleware class.
    """

    def __init__(
        self,
        timeout: float | None = None,
        accumulated_updates_param_name: str = "accumulated",
    ) -> None:
        self._timeout = timeout or DEFAULT_NEW_MESSAGE_TIMEOUT
        self._update_registry: dict[int, list[TelegramObject]] = defaultdict(list)
        self._accumulated_updates_param_name = accumulated_updates_param_name

    def _chat_id_from_event(self, event: TelegramObject) -> int:
        """Extract chat id from event."""
        if isinstance(event, Message):
            return event.chat.id

        raise TypeError("Unexpected event type to accumulate: %r", type(event))

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat_id = self._chat_id_from_event(event)
        self._update_registry[chat_id].append(event)

        last_updates_count = len(self._update_registry[chat_id])

        await asyncio.sleep(self._timeout)
        if last_updates_count != len(self._update_registry[chat_id]):
            return

        data[self._accumulated_updates_param_name] = self._update_registry[chat_id]
        await handler(event, data)
