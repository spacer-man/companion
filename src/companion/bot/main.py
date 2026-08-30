import asyncio
import logging

from agents import Agent, OpenAIProvider, RunConfig
from agents.decorators import tool
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat
from faster_whisper import WhisperModel

from companion.bot.amc import AiogramAMC
from companion.bot.config import Config
from companion.bot.handlers import router

DEFAULT_SYSTEM_MESSAGE = """You are a useful AI companion connected to Telegram via bot.
You should answer to user's messages clearly.

There is a telegram chat with user next:"""


@tool
def get_weather(city: str) -> str:
    return f"It's sunny in {city.title()} now."


async def run() -> None:
    logging.basicConfig(level=logging.DEBUG)
    config = Config()

    agent = Agent(
        name="Main",
        instructions=DEFAULT_SYSTEM_MESSAGE,
        tools=[get_weather],
    )

    run_config = RunConfig(
        model=config.llm_model,
        model_provider=OpenAIProvider(
            api_key="ollama",
            base_url="http://localhost:11434/v1",
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

    dp = Dispatcher(agent=agent, config=config, amc=aiogram_amc, run_config=run_config)

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
