import asyncio
import logging

from agents import Agent, ModelSettings, OpenAIProvider, RunConfig
from agents.extensions.memory import AsyncSQLiteSession
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat
from faster_whisper import WhisperModel
from openai.types import Reasoning

from companion.bot.amc import AiogramAMC
from companion.bot.assistant import TelegramAssistant
from companion.bot.config import AgentConfig
from companion.bot.handlers import router
from companion.bot.mcp_context import mcp_context
from companion.bot.stt import WhisperSTT

CONFIG_FILEPATH = "config.json"

DEFAULT_SYSTEM_MESSAGE = """You are a useful AI companion connected to Telegram via bot.
You should answer to user's messages clearly.


Some formatting instructions:

Date-time formatting is specified by a format string, which must adhere to the following regular expression: r|w?[dD]?[tT]?.

If the format string is empty, the underlying text is displayed as-is; however, the user can still receive the underlying date in their local format. When populated, the format string determines the output based on the presence of the following control characters:

    r: Displays the time relative to the current time. Cannot be combined with any other control characters.
    w: Displays the day of the week in the user's localized language.
    d: Displays the date in short form (e.g., “17.03.22”).
    D: Displays the date in long form (e.g., “March 17, 2022”).
    t: Displays the time in short form (e.g., “22:45”).
    T: Displays the time in long form (e.g., “22:45:00”).

Date-time formatting examples:
![22:45 tomorrow](tg://time?unix=1647531900&format=wDT)
![22:45 tomorrow](tg://time?unix=1647531900&format=t)
![22:45 tomorrow](tg://time?unix=1647531900&format=r)
![22:45 tomorrow](tg://time?unix=1647531900)


Read USER.md and WORKFLOW.md to knew about user and about workflow.

There is a telegram chat with user next:"""

log = logging.getLogger(__name__)


async def run() -> None:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d:%(funcName)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    config = AgentConfig.load(filepath=CONFIG_FILEPATH)

    async with mcp_context(config=config.mcp) as mcp_servers:
        agent = Agent(
            name="Main",
            instructions=DEFAULT_SYSTEM_MESSAGE,
            mcp_servers=mcp_servers,
        )

        run_config = RunConfig(
            model=config.llm.model,
            model_settings=ModelSettings(
                reasoning=Reasoning(effort=config.llm.reasoning_effort),
            ),
            model_provider=OpenAIProvider(
                api_key=(
                    config.llm.api_key.get_secret_value()
                    if config.llm.api_key
                    else None
                ),
                base_url=str(config.llm.base_url) if config.llm.base_url else None,
                use_responses=False,
            ),
            tool_not_found_behavior="return_error_to_model",
        )

        bot_session = None
        if config.telegram.bot_proxy_url:
            bot_session = AiohttpSession(
                proxy=[config.telegram.bot_proxy_url.get_secret_value()],
            )

        bot = Bot(
            token=config.telegram.bot_token.get_secret_value(),
            session=bot_session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        stt = None
        if config.stt and config.stt.active:
            match config.stt.provider:
                case "whisper":
                    config.stt.models_dir.mkdir(parents=True, exist_ok=True)

                    stt = WhisperSTT(
                        model=WhisperModel(
                            model_size_or_path=config.stt.model_size,
                            download_root=config.stt.models_dir.as_posix(),
                            device=config.stt.device,
                        )
                    )

        aiogram_amc = AiogramAMC(bot=bot, stt=stt)

        assistant = TelegramAssistant(
            agent=agent,
            amc=aiogram_amc,
            tg_config=config.telegram,
            session_factory=lambda session_id: AsyncSQLiteSession(
                session_id=session_id, db_path=config.db.db_path
            ),
        )

        dp = Dispatcher(
            assistant=assistant,
            run_config=run_config,
        )

        for telegram_chat_id in config.telegram.owner_ids:
            await bot.set_my_commands(
                commands=[
                    BotCommand(
                        command="/think",
                        description="Set/get current think level.",
                    ),
                    BotCommand(
                        command="/nothink",
                        description="Set think level to 'none'",
                    ),
                ],
                scope=BotCommandScopeChat(chat_id=telegram_chat_id.get_secret_value()),
            )

            # Filter: Allow only owner's events
            router.message.filter(F.chat.id == telegram_chat_id.get_secret_value())

        dp.include_router(router)

        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
