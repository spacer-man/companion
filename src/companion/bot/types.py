from dataclasses import dataclass
from typing import Literal

from companion_core import FuncTool


@dataclass
class BotContext:
    llm_model: str
    llm_reasoning_effort: Literal["none", "low", "high", "max"] | None = None
    agent_tools: list[FuncTool] | None = None
