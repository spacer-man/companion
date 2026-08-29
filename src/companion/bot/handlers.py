import asyncio
import base64
import logging
from collections import defaultdict
from io import BytesIO

from aiogram import Bot, F, Router
from aiogram.filters import Command, or_f
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


@router.message(or_f(F.text, F.photo))
async def handler(message: Message, bot: Bot, agent: Agent, ctx: BotContext) -> None:
    user_message = UserMessage(content=message.text or message.caption)
    if message.photo:
        photo_size = message.photo[-1]
        photo_data = BytesIO()
        photo_file, _ = await asyncio.gather(
            bot.get_file(file_id=photo_size.file_id),
            bot.download(file=photo_size, destination=photo_data),
        )

        # Encode to base64
        image_base64 = base64.b64encode(photo_data.getvalue()).decode("utf-8")
        file_extention = (
            photo_file.file_path.split(".")[-1].lower()
            if photo_file.file_path
            else "jpg"
        )
        user_message.images = [f"data:image/{file_extention};base64,{image_base64}"]

    completions = await agent.ainvoke(
        messages=db[message.chat.id] + [user_message],
        model=ctx.llm_model,
        reasoning_effort=ctx.llm_reasoning_effort,
        tools=ctx.agent_tools,
    )

    for completion in completions:
        db[message.chat.id].append(completion.message)

    if message_text := completions[-1].message.content:
        await message.answer(text=message_text)
