from typing import Self

from agents import RunResultStreaming
from aiogram import Bot
from aiogram.types import InputRichMessage
from aiogram.types import Message as AiogramMessage
from telegramify_markdown.stream import DraftStream
from telegramify_markdown.stream.draft import (
    EntityDraftPayload,
    EntityFinalPayload,
    RichDraftPayload,
    RichFinalPayload,
)

from companion.bot.utils import StateMessage, escape

from .abc import AgentAnswerViewABC


class TelegramifyRichAgentAnswerView(AgentAnswerViewABC):
    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        message_thread_id: int | None = None,
        business_connection_id: str | None = None,
        state_msg_update_delay: float | None = None,
    ) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._message_thread_id = message_thread_id
        self._business_connection_id = business_connection_id
        self._state_msg_update_delay = state_msg_update_delay

    @classmethod
    def from_message(
        cls,
        message: AiogramMessage,
        /,
        *,
        state_msg_update_delay: float | None = None,
    ) -> Self:
        return cls(
            bot=message.bot,  # ty: ignore[invalid-argument-type]
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            business_connection_id=message.business_connection_id,
            state_msg_update_delay=state_msg_update_delay,
        )

    async def stream_answer(self, stream: RunResultStreaming) -> None:
        async def send_draft(payload: RichDraftPayload | EntityDraftPayload) -> None:
            if self._business_connection_id:
                return
            await self._bot.send_rich_message_draft(
                chat_id=self._chat_id,
                draft_id=payload.draft_id,
                message_thread_id=self._message_thread_id,
                rich_message=InputRichMessage(html=payload.rich_message.html),  # ty: ignore[unresolved-attribute]
            )

        async def send_final(payload: RichFinalPayload | EntityFinalPayload) -> None:
            await self._bot.send_rich_message(
                chat_id=self._chat_id,
                message_thread_id=self._message_thread_id,
                business_connection_id=self._business_connection_id,
                rich_message=InputRichMessage(html=payload.rich_message.html),  # ty: ignore[unresolved-attribute]
            )

        state_msg = StateMessage(
            bot=self._bot,
            chat_id=self._chat_id,
            message_thread_id=self._message_thread_id,
            business_connection_id=self._business_connection_id,
            delay=self._state_msg_update_delay,
        )
        show_reasoning: bool = False
        async with DraftStream(
            send_draft=send_draft,
            send_final=send_final,
            interval=0.3,
            thinking_delay=0.5,
        ) as draft_stream:
            async for event in stream.stream_events():
                # We'll ignore the raw responses event deltas
                if event.type == "raw_response_event":
                    if event.data.type == "response.output_text.delta":
                        draft_stream.feed(token=event.data.delta)
                    elif (
                        event.data.type == "response.reasoning_text.delta"
                        and not show_reasoning
                    ):
                        await state_msg.update_text(text="🔶 Thinking...")
                        show_reasoning = True
                    else:
                        continue

                # When the agent updates, print that
                elif event.type == "agent_updated_stream_event":
                    await state_msg.update_text(
                        text=f"🤖 Switch to <code>{escape(event.new_agent.name, '<>')}</code> agent"
                    )
                    continue

                # When items are generated, print them
                elif event.type == "run_item_stream_event":
                    if event.item.type == "tool_call_item":
                        current_tool_name = event.item.tool_name or "unknown"
                        current_tool_name = escape(current_tool_name, "`")
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
                                f' <code>{escape(tool_name, "<>")}</code>'
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

        await state_msg.remove()
