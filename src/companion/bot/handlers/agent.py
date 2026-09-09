import logging

from agents import Agent, RunConfig, Runner
from agents.extensions.memory import AsyncSQLiteSession
from aiogram import Bot, Router
from aiogram.types import InputRichMessage
from aiogram.types import Message as AiogramMessage
from openai.types.responses import (
    ResponseReasoningTextDeltaEvent,
    ResponseTextDeltaEvent,
)
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
    state_msg = StateMessage.from_message(message=message, delay=0.3)
    try:
        if message.audio or message.voice:
            await state_msg.update_text(
                text=f"🎙️ Transcribing {'audio' if message.audio else 'voice'}...",
            )
        user_message, process_msg_meta = await amc.compose(message=message, role="user")

        if not user_message.content:
            raise RuntimeError("user_message.content is empty")

        session = AsyncSQLiteSession(
            session_id=str(message.chat.id),
            db_path=config.db.db_path,
        )
        stream = Runner.run_streamed(
            max_turns=50,
            starting_agent=agent,
            input=user_message.content,
            run_config=run_config,
            session=session,
        )

        if (
            process_msg_meta
            and (transcribed_audio := process_msg_meta.get("transcribed"))
            and config.telegram.personal.send_audio_transcribtion
        ):
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

        show_reasoning: bool = False
        async with DraftStream(
            send_draft=send_draft,
            send_final=send_final,
            interval=0.3,
            thinking_delay=0.5,
            keepalive_timeout=25,
        ) as draft_stream:
            async for event in stream.stream_events():
                # We'll ignore the raw responses event deltas
                if event.type == "raw_response_event":
                    if isinstance(event.data, ResponseTextDeltaEvent):
                        draft_stream.feed(token=event.data.delta)
                    elif (
                        isinstance(event.data, ResponseReasoningTextDeltaEvent)
                        and not show_reasoning
                    ):
                        await state_msg.update_text(text="🔶 Thinking...")
                        show_reasoning = True
                    else:
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
                        current_tool_name = event.item.tool_name or "unknown"
                        current_tool_name = current_tool_name.replace("`", r"\`")
                        tool_alert = (
                            f"\n\n> _🛠️ Tool_ `{current_tool_name}` _was called._\n\n"
                        )
                        draft_stream.feed(token=tool_alert)

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
                        pass

                    else:
                        pass  # Ignore other event types

    except RuntimeError as e:
        await state_msg.update_text(text=f"[ERROR]: {e!r}")
    finally:
        await state_msg.remove()
