import logging
from collections.abc import Callable

from agents import Agent, RunConfig, Runner, SessionABC
from aiogram import Router
from aiogram.types import Message as AiogramMessage

from companion.bot.aa_view import TelegramifyRichAgentAnswerView
from companion.bot.amc import AgentMessageComposerABC
from companion.bot.amc_view import AgentMessageComposeView
from companion.bot.turns_accumulator import TurnsAccumulator

log = logging.getLogger(__name__)


router = Router()


@router.message()
async def handler(
    message: AiogramMessage,
    session_factory: Callable[[str], SessionABC],
    amc: AgentMessageComposerABC,
    amc_view: AgentMessageComposeView,
    turns_accum: TurnsAccumulator,
    agent: Agent,
    run_config: RunConfig,
    max_agent_turns: int = 30,
) -> None:
    session_id = str(message.chat.id)

    input_message = await amc_view.stream_view(role="user", message=message, amc=amc)
    turn = await turns_accum.feed_message(input_message, session_id=session_id)

    if not turn:
        return

    if not turn.content:
        raise ValueError("Input message content is empty!")

    stream = Runner.run_streamed(
        max_turns=max_agent_turns,
        starting_agent=agent,
        input=turn.content,
        run_config=run_config,
        session=session_factory(session_id),
    )

    answer_view = TelegramifyRichAgentAnswerView.from_message(message)
    await answer_view.stream_answer(stream)
