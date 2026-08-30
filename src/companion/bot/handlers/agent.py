import json
import logging
from collections import defaultdict
from typing import Any

from agents import Agent, ItemHelpers, RunConfig, Runner
from aiogram import Router
from aiogram.types import Message as AiogramMessage
from companion_core import AnyMessage, SystemMessage

from companion.bot.amc import AgentMessageComposer
from companion.bot.config import Config
from companion.bot.utils import StateMessage, wrap_chat_action

log = logging.getLogger(__name__)


DEFAULT_SYSTEM_MESSAGE = """You are a useful AI companion connected to Telegram via bot.
You should answer to user's messages clearly.

There is a telegram chat with user next:"""

db: dict[int, list[AnyMessage]] = defaultdict(
    lambda: [SystemMessage(content=DEFAULT_SYSTEM_MESSAGE)]
)


router = Router()


def escape_html(text: str) -> str:
    return text.replace(">", r"\>").replace("<", r"\<")


@router.message()
@wrap_chat_action()
async def handler(
    message: AiogramMessage,
    agent: Agent,
    config: Config,
    run_config: RunConfig,
    amc: AgentMessageComposer,
) -> None:
    user_message = await amc.compose(message=message, role="user")

    if not user_message.content:
        raise RuntimeError("user_message.content is empty")

    stream = Runner.run_streamed(
        starting_agent=agent,
        input=user_message.content,
        run_config=run_config,
    )

    if config.reply_transcribed_voice and user_message.content:
        message_content: dict[str, Any] = json.loads(user_message.content)
        transcribed_audio: str | None = message_content.get("voice")
        if transcribed_audio:
            await message.reply(
                text=f"[Transcribed audio]:\n<codeblock>{escape_html(transcribed_audio)}</codeblock>"
            )

    state_msg = StateMessage(initial_message=message)
    async for event in stream.stream_events():
        # We'll ignore the raw responses event deltas
        if event.type == "raw_response_event":
            continue
        # When the agent updates, print that
        elif event.type == "agent_updated_stream_event":
            await state_msg.update_text(
                text=f"🤖 Switch to <code>{escape_html(event.new_agent.name)}</code> agent"
            )
            continue
        # When items are generated, print them
        elif event.type == "run_item_stream_event":
            if event.item.type == "tool_call_item":
                await state_msg.update_text(
                    text=f"🛠️ Tool <code>{escape_html(str(event.item.tool_name))}</code> was called"
                )
            elif event.item.type == "tool_call_output_item":
                tool_name: str | None = None
                if tool := event.item.tool_origin:
                    tool_name = tool.agent_tool_name
                await state_msg.update_text(
                    text=f"🧠 Analyze{
                        f' <code>{escape_html(tool_name)}</code>' if tool_name else ''
                    } tool results..."
                )
            elif event.item.type == "reasoning_item":
                reasoning = event.item.raw_item.summary
                await state_msg.update_text(
                    text=f"💭 <i>{escape_html(reasoning[0].text if reasoning else 'None')}</i>"
                )
            elif event.item.type == "message_output_item":
                await state_msg.update_text(
                    text=escape_html(ItemHelpers.text_message_output(event.item)),
                    ensure_updated=True,
                )
                break
            else:
                pass  # Ignore other event types
