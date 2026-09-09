import asyncio
from asyncio.tasks import Task
from collections.abc import Callable

from agents import Agent, RunConfig, Runner, SessionABC
from aiogram.types import Message as AiogramMessage
from companion_core.types import Message

from companion.bot.agent_answer_view import AgentAnswerViewABC
from companion.bot.amc import AgentMessageComposer
from companion.bot.config import TelegramConfig
from companion.bot.message_storage import InmemoryMessageStorage, MessageStorageABC
from companion.bot.turn_composer import SimpleTurnComposer, TurnComposerABC
from companion.bot.utils import StateMessage, escape, wrap_chat_action

DEFAULT_NEW_MESSAGE_TIMEOUT = 5


class TelegramAssistant:
    """Main telegram assistant class."""

    def __init__(
        self,
        agent: Agent,
        amc: AgentMessageComposer[AiogramMessage],
        tg_config: TelegramConfig,
        turn_composer: TurnComposerABC | None = None,
        session_factory: Callable[[str], SessionABC] | None = None,
        message_storage: MessageStorageABC | None = None,
        new_message_timeout: float | None = None,
    ) -> None:
        self._agent = agent
        self._amc = amc
        self._tg_config = tg_config
        self._turn_composer = turn_composer or SimpleTurnComposer()
        self._session_factory = session_factory
        self._message_storage = message_storage or InmemoryMessageStorage()
        self._new_message_timeout = new_message_timeout or DEFAULT_NEW_MESSAGE_TIMEOUT

    def feed_message(
        self,
        message: AiogramMessage,
        session_id: str,
        answer_view: AgentAnswerViewABC,
        run_config: RunConfig | None = None,
        max_agent_turns: int | None = 30,
    ) -> Task:

        async def _feed_message() -> None:
            processed = await self._preprocess_message(message)
            await self._message_storage.store(processed, session_id=session_id)

            last_stored_messages_count = await self._message_storage.count(session_id)
            await asyncio.sleep(self._new_message_timeout)

            if last_stored_messages_count != await self._message_storage.count(
                session_id=session_id,
            ):
                return

            messages_turn = await self._message_storage.pop(session_id)
            turn = await self._turn_composer.compose_turn(
                role=processed.role,
                messages=messages_turn,
            )
            await self._process_turn(
                turn=turn,
                session_id=session_id,
                answer_view=answer_view,
                run_config=run_config,
                max_agent_turns=max_agent_turns,
            )

        return asyncio.create_task(_feed_message())

    @wrap_chat_action()
    async def _preprocess_message(
        self,
        message: AiogramMessage,
        state_message: StateMessage | None = None,
    ) -> Message:
        delete_state_message: bool = False
        if not state_message:
            delete_state_message: bool = True
            state_message = StateMessage.from_message(message=message)
        if message.audio or message.voice:
            await state_message.update_text(
                text=f"🎙️ Transcribing {'audio' if message.audio else 'voice'}...",
            )
        processed, process_msg_meta = await self._amc.compose(
            message=message,
            role="user",
        )

        if not processed.content:
            raise ValueError("user_message.content is empty")

        if (
            process_msg_meta
            and (transcribed_audio := process_msg_meta.get("transcribed"))
            and self._tg_config.personal.send_audio_transcribtion
        ):
            await message.reply(
                text=f"<pre><code>{escape(transcribed_audio, '<>')}</code></pre>",
            )

        if delete_state_message:
            await state_message.remove()

        return processed

    @wrap_chat_action()
    async def _process_turn(
        self,
        turn: Message,
        session_id: str,
        answer_view: AgentAnswerViewABC,
        run_config: RunConfig | None,
        max_agent_turns: int | None = None,
    ) -> None:
        if not turn.content:
            raise ValueError("user_message.content is empty")

        session = None
        if self._session_factory:
            session = self._session_factory(session_id)

        stream = Runner.run_streamed(
            max_turns=max_agent_turns,
            starting_agent=self._agent,
            input=turn.content,
            run_config=run_config,
            session=session,
        )
        await answer_view.iterate_stream(stream)
