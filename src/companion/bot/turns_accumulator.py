import asyncio
import time
from collections.abc import Callable

from agents import Agent, SessionABC
from companion_core.types import Message

from companion.bot.amc import AgentMessageComposerABC
from companion.bot.amc_view import AgentMessageComposeView, EmptyAgentMessageComposeView
from companion.bot.config import TelegramConfig
from companion.bot.message_storage import InmemoryMessageStorage, MessageStorageABC
from companion.bot.turn_composer import SimpleTurnComposer, TurnComposerABC

DEFAULT_NEW_MESSAGE_TIMEOUT = 5
CHECK_TIMEOUT_INTERVAL = 1


type Turn = Message


class TurnsAccumulator:
    """TurnsAccumulator."""

    def __init__(
        self,
        agent: Agent,
        amc: AgentMessageComposerABC,
        tg_config: TelegramConfig,
        amc_view: AgentMessageComposeView | None = None,
        turn_composer: TurnComposerABC | None = None,
        session_factory: Callable[[str], SessionABC] | None = None,
        message_storage: MessageStorageABC | None = None,
        new_message_timeout: float | None = None,
    ) -> None:
        self._agent = agent
        self._amc = amc
        self._amc_view = amc_view or EmptyAgentMessageComposeView()
        self._tg_config = tg_config
        self._turn_composer = turn_composer or SimpleTurnComposer()
        self._session_factory = session_factory
        self._message_storage = message_storage or InmemoryMessageStorage()
        self._new_message_timeout = new_message_timeout or DEFAULT_NEW_MESSAGE_TIMEOUT

    async def feed_message(
        self,
        message: Message,
        session_id: str,
    ) -> Turn | None:
        """Return Trun if accumulated else None."""
        await self._message_storage.store(message, session_id=session_id)

        last_stored_messages_count = await self._message_storage.count(session_id)

        time_checkpoint = time.monotonic()
        while time.monotonic() - time_checkpoint:
            await asyncio.sleep(CHECK_TIMEOUT_INTERVAL)

            if last_stored_messages_count != await self._message_storage.count(
                session_id=session_id,
            ):
                return

        turn_messages = await self._message_storage.pop(session_id)
        turn = await self._turn_composer.compose_turn(
            role=message.role,
            messages=turn_messages,
        )
        return turn
