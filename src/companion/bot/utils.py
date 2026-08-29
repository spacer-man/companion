import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from functools import wraps
from typing import ParamSpec, TypeVar

from aiogram import Bot
from aiogram.types import CallbackQuery, Message

P = ParamSpec("P")
R = TypeVar("R")

DEFAULT_CHAT_ACTION_TIMEOUT = 3 * 60
CHAT_ACTION_UPDATE_DELAY = 4


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
            event: Message | CallbackQuery = args[0]  # ty: ignore[invalid-assignment]

            business_connection_id = None
            message_thread_id = None
            if isinstance(event, Message):
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
