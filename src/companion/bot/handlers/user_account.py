import logging
from collections.abc import Callable

from agents import Agent, RunConfig, Runner, SessionABC
from aiogram import Router
from aiogram.types import Message as AiogramMessage

from companion.bot.aa_view import TelegramifyAgentAnswerView
from companion.bot.amc import AgentMessageComposerABC
from companion.bot.config import AgentConfig
from companion.bot.turns_accumulator import TurnsAccumulator

log = logging.getLogger(__name__)

router = Router(name="user_account")


@router.business_message()
async def process_user_account_message(
    message: AiogramMessage,
    session_factory: Callable[[str], SessionABC],
    amc: AgentMessageComposerABC,
    agent: Agent,
    turns_accum: TurnsAccumulator,
    run_config: RunConfig,
    config: AgentConfig,
    max_agent_turns: int = 30,
) -> None:
    session_id = f"ua:{message.chat.id}"  # 'ua:' - user account's session prefix

    if (
        not (msg_text := message.text or message.caption)
        or not msg_text.startswith(config.telegram.call_agent_prefix)
        or not message.from_user
        or message.from_user.id not in config.telegram.owner_ids
    ):
        return

    input_message = await amc.compose(role="user", message=message)
    turn = await turns_accum.feed_message(message=input_message, session_id=session_id)
    if not turn:  # If turn was edited then return
        return

    if not turn.content:
        raise ValueError("Turn content is empty!")

    stream = Runner.run_streamed(
        max_turns=max_agent_turns,
        starting_agent=agent,
        input=turn.content,
        run_config=run_config,
        session=session_factory(session_id),
    )
    answer_view = TelegramifyAgentAnswerView.from_message(message)
    await answer_view.stream_answer(stream)
