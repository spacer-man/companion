from dataclasses import dataclass

from companion_core import FuncTool

from companion.bot.config import Config


@dataclass
class BotContext:
    config: Config
    agent_tools: list[FuncTool] | None = None
