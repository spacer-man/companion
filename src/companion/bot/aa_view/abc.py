from abc import ABC, abstractmethod

from agents import RunResultStreaming


class AgentAnswerViewABC(ABC):
    @abstractmethod
    async def stream_answer(self, stream: RunResultStreaming) -> None: ...
