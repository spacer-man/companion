import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    Message,
)
from companion_core import Agent, AnyMessage, SystemMessage

from companion.bot.amc import AgentMessageComposer
from companion.bot.types import BotContext
from companion.bot.utils import wrap_chat_action

log = logging.getLogger(__name__)


DEFAULT_SYSTEM_MESSAGE = """You are a useful AI companion connected to Telegram via bot.
You should answer to user's messages clearly.

There is a telegram chat with user next:"""

db: dict[int, list[AnyMessage]] = defaultdict(
    lambda: [SystemMessage(content=DEFAULT_SYSTEM_MESSAGE)]
)


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
        llm_reasoning_effort = ctx.config.llm_reasoning_effort
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

    ctx.config.llm_reasoning_effort = level
    alert = await message.answer(text=f"The think level was setted to '{level}'")
    await asyncio.sleep(3)
    await alert.delete()


@router.message()
@wrap_chat_action()
async def handler(
    message: Message,
    agent: Agent,
    ctx: BotContext,
    amc: AgentMessageComposer,
) -> None:
    user_message = await amc.compose(message=message, role="user")

    if ctx.config.reply_transcribed_audio and user_message.content:
        message_content: dict[str, Any] = json.loads(user_message.content)
        transcribed_audio: str | None = message_content.get("audio")
        if transcribed_audio:
            escaped_audio = transcribed_audio.replace("`", r"\`")
            await message.reply(text=f"\\[Transcribed audio\\]:\n```{escaped_audio}```")

    completions = await agent.ainvoke(
        messages=db[message.chat.id] + [user_message],
        model=ctx.config.llm_model,
        reasoning_effort=ctx.config.llm_reasoning_effort,
        tools=ctx.agent_tools,
    )

    for completion in completions:
        db[message.chat.id].append(completion.message)

    if message_text := completions[-1].message.content:
        await message.answer(text=message_text)
