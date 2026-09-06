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
from companion.bot.mcps.gcal import gcal_mcp_context

GOOGLE_CALENDAR_CREDS_FILE = "secrets/google_calendar_token.json"

DEFAULT_SYSTEM_MESSAGE = """You are a useful AI companion connected to Telegram via bot.
You should answer to user's messages clearly.

Format your answer in telegram HTML markup please. The following tags are currently supported:

<b>bold</b>, <strong>bold</strong>
<i>italic</i>, <em>italic</em>
<u>underline</u>, <ins>underline</ins>
<s>strikethrough</s>, <strike>strikethrough</strike>, <del>strikethrough</del>
<span class="tg-spoiler">spoiler</span>, <tg-spoiler>spoiler</tg-spoiler>
<b>bold <i>italic bold <s>italic bold strikethrough <span class="tg-spoiler">italic bold strikethrough spoiler</span></s> <u>underline italic bold</u></i> bold</b>
<a href="http://www.example.com/">inline URL</a>
<a href="tg://user?id=123456789">inline mention of a user</a>
<tg-emoji emoji-id="5368324170671202286">👍</tg-emoji>
<tg-time unix="1647531900" format="wDT">22:45 tomorrow</tg-time>
<tg-time unix="1647531900" format="t">22:45 tomorrow</tg-time>
<tg-time unix="1647531900" format="r">22:45 tomorrow</tg-time>
<tg-time unix="1647531900">22:45 tomorrow</tg-time>
<code>inline fixed-width code</code>
<pre>pre-formatted fixed-width code block</pre>
<pre><code class="language-python">pre-formatted fixed-width code block written in the Python programming language</code></pre>
<blockquote>Block quotation started
Block quotation continued
The last line of the block quotation</blockquote>
<blockquote expandable>Expandable block quotation started
Expandable block quotation continued
Expandable block quotation continued
Hidden by default part of the block quotation started
Expandable block quotation continued
The last line of the block quotation</blockquote>

Please note:

    Only the tags mentioned above are currently supported.
    All <, > and & symbols that are not a part of a tag or an HTML entity must be replaced with the corresponding HTML entities (< with &lt;, > with &gt; and & with &amp;).
    All numerical HTML entities are supported.
    The API currently supports only the following named HTML entities: &lt;, &gt;, &amp; and &quot;.
    Use nested pre and code tags, to define programming language for pre entity.
    Programming language can't be specified for standalone code tags.
    A valid emoji must be used as the content of the tg-emoji tag. The emoji will be shown instead of the custom emoji in places where a custom emoji cannot be displayed (e.g., system notifications) or if the message is forwarded by a non-premium user. It is recommended to use the emoji from the emoji field of the custom emoji sticker.
    Custom emoji entities can only be used by bots that purchased additional usernames on Fragment or in the messages directly sent by the bot to private, group and supergroup chats if the owner of the bot has a Telegram Premium subscription.
    See date-time entity formatting for more details about supported date-time formats.

There is a telegram chat with user next:"""


@tool
def get_weather(city: str) -> str:
    return f"It's sunny in {city.title()} now."


async def run() -> None:
    logging.basicConfig(level=logging.DEBUG)
    config = Config()

    async with gcal_mcp_context(creds_file=GOOGLE_CALENDAR_CREDS_FILE) as gcal_mcp:
        agent = Agent(
            name="Main",
            instructions=DEFAULT_SYSTEM_MESSAGE,
            tools=[get_weather],
            mcp_servers=[gcal_mcp],
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
