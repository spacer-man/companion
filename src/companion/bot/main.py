import asyncio
import logging

from agents import Agent, ModelSettings, OpenAIProvider, RunConfig
from agents.decorators import tool
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat
from faster_whisper import WhisperModel
from openai.types import Reasoning

from companion.bot.amc import AiogramAMC
from companion.bot.config import Config
from companion.bot.handlers import router
from companion.bot.mcps.google_workspace import google_workspace_mcp

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


There is a telegram chat with user next:"""

log = logging.getLogger(__name__)


@tool
def get_weather(city: str) -> str:
    return f"It's sunny in {city.title()} now."


async def run() -> None:
    logging.basicConfig(level=logging.DEBUG)
    config = Config()

    async with google_workspace_mcp() as gworkspace_mcp:
        agent = Agent(
            name="Main",
            instructions=DEFAULT_SYSTEM_MESSAGE,
            tools=[get_weather],
            mcp_servers=[gworkspace_mcp],
        )

        run_config = RunConfig(
            model=config.llm_model,
            model_settings=ModelSettings(
                reasoning=Reasoning(effort=config.llm_reasoning_effort),
            ),
            model_provider=OpenAIProvider(
                api_key=(
                    config.llm_api_key.get_secret_value()
                    if config.llm_api_key
                    else None
                ),
                base_url=config.llm_base_url,
                use_responses=False,
            ),
        )

        bot_session = None
        if config.tg_bot_proxy:
            bot_session = AiohttpSession(
                proxy=[config.tg_bot_proxy.get_secret_value()],
            )

        bot = Bot(
            token=config.tg_bot_token.get_secret_value(),
            session=bot_session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        await config.stt_models_dir.mkdir(parents=True, exist_ok=True)

        whisper_model = WhisperModel(
            model_size_or_path=config.stt_model_size,
            download_root=config.stt_models_dir.as_posix(),
            device=config.stt_device,
        )

        aiogram_amc = AiogramAMC(
            bot=bot,
            whisper_model=whisper_model,
        )

        dp = Dispatcher(
            agent=agent,
            config=config,
            amc=aiogram_amc,
            run_config=run_config,
        )

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
            scope=BotCommandScopeChat(chat_id=config.tg_owner_id.get_secret_value()),
        )

        dp.include_router(router)

        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
