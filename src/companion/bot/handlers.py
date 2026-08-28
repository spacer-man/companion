import asyncio
import logging
from collections import defaultdict

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    Message,
)
from companion_core import Agent, UserMessage
from companion_core.types import AnyMessage

from companion.bot.types import BotContext

log = logging.getLogger(__name__)


db: dict[int, list[AnyMessage]] = defaultdict(list)


router = Router()


@router.message(Command(commands=["think", "nothink"]))
async def set_think_level(message: Message, ctx: BotContext) -> None:
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
        await message.answer(
            text=f"The current think level is equal to '{ctx.llm_reasoning_effort}'"
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

    ctx.llm_reasoning_effort = level
    alert = await message.answer(text=f"The think level was setted to '{level}'")
    await asyncio.sleep(3)
    await alert.delete()


@router.message(F.text)
async def handler(message: Message, agent: Agent, ctx: BotContext) -> None:
    async for completions in agent.astream(
        messages=db[message.chat.id] + [UserMessage(content=message.text)],
        model=ctx.llm_model,
        stream_content=False,
        reasoning_effort=ctx.llm_reasoning_effort,
        tools=ctx.agent_tools,
    ):
        completion = completions[-1]
        if (
            message_text := completion.message.content
        ) and completion.message.role == "assistant":
            await message.answer(text=message_text)

    for completion in completions:
        db[message.chat.id].append(completion.message)
