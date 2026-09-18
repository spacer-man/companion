from typing import Self

from agents import ItemHelpers, RunResultStreaming
from aiogram import Bot
from aiogram.types import Message as AiogramMessage

from companion.bot.utils import StateMessage, escape

from .abc import AgentAnswerViewABC


class TelegramifyAgentAnswerView(AgentAnswerViewABC):
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

        state_msg = StateMessage(
            bot=self._bot,
            chat_id=self._chat_id,
            message_thread_id=self._message_thread_id,
            business_connection_id=self._business_connection_id,
            delay=self._state_msg_update_delay,
        )
        show_reasoning: bool = False
        async for event in stream.stream_events():
            # We'll ignore the raw responses event deltas
            if event.type == "raw_response_event":
                if (
                    event.data.type == "response.reasoning_text.delta"
                    and not show_reasoning
                ):
                    await state_msg.update_text(text="🔶 Thinking...")
                    show_reasoning = True
                else:
                    continue

            # When the agent updates, print that
            elif event.type == "agent_updated_stream_event":
                agent_name = escape(event.new_agent.name, "<>")
                await state_msg.update_text(
                    text=f"🤖 Switch to <code>{agent_name}</code> agent"
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
                    await state_msg.update_text(text=tool_alert)

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

                elif event.item.type == "message_output_item":
                    await state_msg.update_text(
                        text=(
                            ItemHelpers.extract_text(event.item.raw_item)
                            or "Nothing to say"
                        ),
                        ensure_updated=True,
                    )

                else:
                    pass  # Ignore other event types
