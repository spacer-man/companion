import json
import logging
from collections import defaultdict
from typing import Any

from aiogram import Router
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


@router.message()
@wrap_chat_action()
async def handler(
    message: Message,
    agent: Agent,
    ctx: BotContext,
    amc: AgentMessageComposer,
) -> None:
    user_message = await amc.compose(message=message, role="user")

    if ctx.config.reply_transcribed_voice and user_message.content:
        message_content: dict[str, Any] = json.loads(user_message.content)
        transcribed_audio: str | None = message_content.get("voice")
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
