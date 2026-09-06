import asyncio
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    Message,
)

from companion.bot.config import AgentConfig

log = logging.getLogger(__name__)


router = Router()


@router.message(Command(commands=["think", "nothink"]))
async def set_think_level(message: Message, config: AgentConfig) -> None:
    if not message.text:
        raise RuntimeError("message.text is None")

    await message.delete()

    command, *params = message.text.split()

    if command == "/nothink":
        params = ["none"]

    if len(params) > 1:
        alert = await message.answer(
            text="The think level can't get more than 1 parameter"
        )
        await asyncio.sleep(3)
        await alert.delete()
        return

    elif len(params) == 0:
        llm_reasoning_effort = config.llm.reasoning_effort
        await message.answer(
            text=f"The current think level is equal to '{llm_reasoning_effort}'"
        )
        return

    level = params[0]
    if level not in ("none", "low", "high", "max"):
        alert = await message.answer(
            text="The think level can be only equal to 'none', 'low', 'hight' or 'max'"
        )
        await asyncio.sleep(3)
        await alert.delete()
        return

    config.llm.reasoning_effort = level
    alert = await message.answer(text=f"The think level was setted to '{level}'")
    await asyncio.sleep(3)
    await alert.delete()
