import json
import logging
from typing import Any

from agents import Agent, ItemHelpers, RunConfig, Runner
from agents.extensions.memory import AsyncSQLiteSession
from aiogram import Bot, Router
from aiogram.types import InputRichMessage
from aiogram.types import Message as AiogramMessage
from telegramify_markdown.stream import DraftStream
from telegramify_markdown.stream.draft import (
    EntityDraftPayload,
    EntityFinalPayload,
    RichDraftPayload,
    RichFinalPayload,
)

from companion.bot.amc import AgentMessageComposer
from companion.bot.config import AgentConfig
from companion.bot.utils import StateMessage, wrap_chat_action

log = logging.getLogger(__name__)


router = Router()


def escape_html(text: str) -> str:
    return text.replace(">", r"\>").replace("<", r"\<")


@router.message()
@wrap_chat_action()
async def handler(
    message: AiogramMessage,
    bot: Bot,
    agent: Agent,
    config: AgentConfig,
    run_config: RunConfig,
    amc: AgentMessageComposer,
) -> None:
    state_msg = StateMessage(initial_message=message, delay=0.3)
    try:
        if message.audio or message.voice:
            await state_msg.update_text(
                text=f"Transcribing {'audio' if message.audio else 'voice'}...",
            )
        user_message = await amc.compose(message=message, role="user")

        if not user_message.content:
            raise RuntimeError("user_message.content is empty")

        session = AsyncSQLiteSession(
            session_id=str(message.chat.id),
            db_path=config.db.db_path,
        )
        stream = Runner.run_streamed(
            starting_agent=agent,
            input=user_message.content,
            run_config=run_config,
            session=session,
        )

        if config.telegram.personal.send_audio_transcribtion and user_message.content:
            message_content: dict[str, Any] = json.loads(user_message.content)
            transcribed_audio: str | None = message_content.get("voice")
            if transcribed_audio:
                await message.reply(
                    text=f"<pre><code>{escape_html(transcribed_audio)}</code></pre>"
                )

        async def send_draft(payload: RichDraftPayload | EntityDraftPayload) -> None:
            await bot.send_rich_message_draft(
                chat_id=message.chat.id,
                draft_id=payload.draft_id,
                rich_message=InputRichMessage(html=payload.rich_message.html),  # ty: ignore[unresolved-attribute]
            )

        async def send_final(payload: RichFinalPayload | EntityFinalPayload) -> None:
            await bot.send_rich_message(
                chat_id=message.chat.id,
                rich_message=InputRichMessage(html=payload.rich_message.html),  # ty: ignore[unresolved-attribute]
            )

        final_answer = ""
        async with DraftStream(
            send_draft=send_draft,
            send_final=send_final,
            interval=0.3,
            thinking_delay=0.5,
            keepalive_timeout=25,
            cancel_clears_draft=False,
        ) as draft_stream:
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
                                f' <code>{escape_html(tool_name)}</code>'
                                if tool_name
                                else ''
                            } tool results..."
                        )

                    elif event.item.type == "reasoning_item":
                        reasoning = event.item.raw_item.summary
                        if reasoning:
                            draft_stream.feed(token=reasoning[0].text)

                    elif event.item.type == "message_output_item":
                        answer = ItemHelpers.text_message_output(event.item)
                        final_answer += answer
                        draft_stream.feed(token=final_answer)
                        break

                    else:
                        pass  # Ignore other event types

    except RuntimeError as e:
        await state_msg.update_text(text=f"[ERROR]: {e!r}")
    finally:
        await state_msg.remove()
