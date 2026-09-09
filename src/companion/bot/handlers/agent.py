import logging

from agents import RunConfig
from aiogram import Bot, Router
from aiogram.types import Message as AiogramMessage

from companion.bot.agent_answer_view import AiogramAgentAnswerView
from companion.bot.assistant import TelegramAssistant

log = logging.getLogger(__name__)


router = Router()


@router.message()
async def handler(
    message: AiogramMessage,
    bot: Bot,
    assistant: TelegramAssistant,
    run_config: RunConfig,
) -> None:
    await assistant.feed_message(
        message,
        session_id=str(message.chat.id),
        answer_view=AiogramAgentAnswerView(bot=bot, chat_id=message.chat.id),
        run_config=run_config,
    )
