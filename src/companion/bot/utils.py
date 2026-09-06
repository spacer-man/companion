import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from functools import wraps
from typing import ParamSpec, TypeVar

from aiogram import Bot
from aiogram.types import CallbackQuery
from aiogram.types import Message as AiogramMessage

P = ParamSpec("P")
R = TypeVar("R")

DEFAULT_CHAT_ACTION_TIMEOUT = 3 * 60
CHAT_ACTION_UPDATE_DELAY = 4
DEFAULT_POSSIBILITY_TO_UPDATE_CHECK_DELAY = 1


log = logging.getLogger(__name__)


async def chat_action(
    chat_id: int | str,
    bot: Bot,
    action: str,
    business_connection_id: str | None = None,
    message_thread_id: int | None = None,
    timeout: int | None = None,
) -> None:
    if timeout is None:
        timeout = DEFAULT_CHAT_ACTION_TIMEOUT

    start_time = time.monotonic()
    while True:
        await bot.send_chat_action(
            chat_id=chat_id,
            action=action,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
        )

        if time.monotonic() - start_time > timeout:
            break

        await asyncio.sleep(CHAT_ACTION_UPDATE_DELAY)


def wrap_chat_action(
    action: str = "typing",
    timeout: int | None = None,
) -> Callable[
    [Callable[P, Awaitable[R]]],
    Callable[P, Awaitable[R]],
]:
    def decorator(
        func: Callable[P, Awaitable[R]],
    ) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            event: AiogramMessage | CallbackQuery = args[0]  # ty: ignore[invalid-assignment]

            business_connection_id = None
            message_thread_id = None
            if isinstance(event, AiogramMessage):
                chat_id = event.chat.id
                business_connection_id = event.business_connection_id
                message_thread_id = event.message_thread_id
            elif isinstance(event, CallbackQuery) and event.message:
                chat_id = event.message.chat.id
            else:
                raise ValueError("Not found chat id in received event")

            chat_action_task = asyncio.create_task(
                chat_action(
                    chat_id=chat_id,
                    bot=event.bot,  # ty: ignore[invalid-argument-type]
                    action=action,
                    business_connection_id=business_connection_id,
                    message_thread_id=message_thread_id,
                    timeout=timeout,
                )
            )

            try:
                return await func(*args, **kwargs)
            finally:
                chat_action_task.cancel()

                with suppress(asyncio.CancelledError):
                    await chat_action_task

        return wrapper

    return decorator


class StateMessage:
    """Class that simplify displaying & updating state message."""

    def __init__(
        self,
        initial_message: AiogramMessage,
        delay: float | None = None,
    ) -> None:
        self._delay = delay or CHAT_ACTION_UPDATE_DELAY
        self._init_message = initial_message
        self._message: AiogramMessage | None = None
        self._last_update: float | None = None
        self._last_content: str | None = None

    async def _send_update(
        self,
        update_callback: Callable[[], Awaitable],
        ensure_updated: bool = False,
        check_delay: int | None = None,
    ) -> bool:
        if not check_delay:
            check_delay = DEFAULT_POSSIBILITY_TO_UPDATE_CHECK_DELAY
        is_updated = False

        while True:
            if (
                self._last_update is None
                or self._last_update + self._delay <= time.monotonic()
            ):
                await update_callback()
                self._last_update = time.monotonic()
                is_updated = True

            if not ensure_updated or is_updated:
                break

            await asyncio.sleep(check_delay)

        return is_updated

    async def update_text(
        self,
        text: str,
        ensure_updated: bool = False,
        check_delay: int | None = None,
    ) -> None:
        async def callback():
            if self._last_content == text:
                return

            if self._message:
                await self._message.edit_text(text=text)
            else:
                self._message = await self._init_message.answer(text=text)

            self._last_content = text

        while True:
            is_updated = await self._send_update(callback, ensure_updated, check_delay)
            if not ensure_updated or is_updated:
                break

    async def remove(self) -> None:
        if self._message:
            await self._message.delete()
