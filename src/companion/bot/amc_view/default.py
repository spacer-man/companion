from aiogram.types import Message as AiogramMessage
from companion_core import AnyMessage

from companion.bot.amc import AgentMessageComposerABC
from companion.bot.utils import StateMessage, escape

from .abc import AgentMessageComposeView


class SimpleAgentMessageComposeView(AgentMessageComposeView):
    async def stream_view(
        self,
        role: str,
        message: AiogramMessage,
        amc: AgentMessageComposerABC,
    ) -> AnyMessage:
        state_msg = StateMessage.from_message(message=message)

        input_message = None
        async for event in amc.stream_compose(message=message, role=role):
            match event.data.type:
                case "audio.transcribing.start":
                    await state_msg.update_text(
                        text=f"🎙️ Transcribing {'audio' if message.audio else 'voice'}...",
                    )
                case "audio.transcribing.done":
                    if transcribed := event.data.transcribed:
                        await message.reply(
                            text=f"<pre><code>{escape(transcribed, '<>')}</code></pre>",
                        )
                case "done":
                    input_message = event.data.message

        await state_msg.remove()

        if not input_message:
            raise RuntimeError("Failded to compose input message")

        return input_message
