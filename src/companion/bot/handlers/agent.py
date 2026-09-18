import logging
from collections.abc import Callable

from agents import Agent, RunConfig, Runner, SessionABC
from aiogram import Router
from aiogram.types import Message as AiogramMessage

from companion.bot.aa_view import TelegramifyAgentAnswerView
from companion.bot.amc import AgentMessageComposerABC
from companion.bot.amc_view import AgentMessageComposeView

log = logging.getLogger(__name__)


router = Router()


@router.message()
async def handler(
    message: AiogramMessage,
    session_factory: Callable[[str], SessionABC],
    amc: AgentMessageComposerABC,
    amc_view: AgentMessageComposeView,
    agent: Agent,
    run_config: RunConfig,
    max_agent_turns: int = 30,
) -> None:
    input_message = await amc_view.stream_view(role="user", message=message, amc=amc)

    if not input_message.content:
        raise ValueError("Input message content is empty!")

    stream = Runner.run_streamed(
        max_turns=max_agent_turns,
        starting_agent=agent,
        input=input_message.content,
        run_config=run_config,
        session=session_factory(str(message.chat.id)),
    )

    answer_view = TelegramifyAgentAnswerView.from_message(message)
    await answer_view.stream_answer(stream)
