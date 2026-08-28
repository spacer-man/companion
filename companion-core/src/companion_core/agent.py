import json
from collections.abc import AsyncGenerator, Iterable
from typing import Literal, Self

from companion_core.llm import LLM
from companion_core.tools import FuncTool, ToolManager
from companion_core.types import (
    AnyMessage,
    Completion,
    Message,
    ToolCall,
    ToolCallError,
    ToolMessage,
)


class Agent:
    def __init__(
        self,
        llm: LLM,
        tool_call_error_ok: bool = False,
    ) -> None:
        self._llm = llm
        self._tool_call_error_ok = tool_call_error_ok

    async def _exec_tool_calls(
        self,
        tool_calls: list[ToolCall],
        tool_manager: ToolManager,
    ) -> AsyncGenerator[ToolMessage]:
        for tool_call in tool_calls:
            if tool_call.type == "function":
                tool_name = tool_call.function.name
                try:
                    execute_result = await tool_manager.aexecute(
                        name=tool_name,
                        kwargs=json.loads(tool_call.function.arguments),
                    )
                except Exception as e:
                    if self._tool_call_error_ok:
                        yield ToolMessage(
                            content=f"[Executing '{tool_name}' error]: {e!r}",
                        )
                    else:
                        raise ToolCallError from e
                else:
                    yield ToolMessage(
                        content=f"[Executing '{tool_name}' result]: {execute_result}",
                    )

    async def ainvoke(
        self,
        messages: Iterable[Message],
        model: str,
        reasoning_effort: Literal["none", "low", "high", "max"] | None = None,
        tools: Iterable[FuncTool] | None = None,
    ) -> list[Completion[AnyMessage]]:
        tm = ToolManager()
        for _tool in tools or []:
            tm.register(_tool)

        completions = [Completion(message=m) for m in messages]

        while True:
            completion = await self._llm.ainvoke(
                messages=[c.message for c in completions],
                model=model,
                reasoning_effort=reasoning_effort,
                tools=tools,
            )

            completions.append(completion)

            match completion.finish_reason:
                case "stop" | "length":
                    break
                case "tool_calls":
                    tool_calls = completion.message.tool_calls
                    if not tool_calls:
                        break
                    async for tool_message in self._exec_tool_calls(
                        tool_calls=tool_calls,
                        tool_manager=tm,
                    ):
                        completions.append(Completion(message=tool_message))

        return completions

    async def astream(
        self,
        messages: Iterable[Message],
        model: str,
        stream_content: bool = False,
        reasoning_effort: Literal["none", "low", "high", "max"] | None = None,
        tools: Iterable[FuncTool] | None = None,
    ) -> AsyncGenerator[list[Completion[AnyMessage]]]:
        tm = ToolManager()
        for _tool in tools or []:
            tm.register(_tool)

        completions = [Completion(message=m) for m in messages]

        while True:
            if stream_content:
                async for streaming_completion in self._llm.astream(
                    messages=[c.message for c in completions],
                    model=model,
                    reasoning_effort=reasoning_effort,
                    tools=tools,
                ):
                    yield completions + [streaming_completion]
                completions.append(streaming_completion)
            else:
                completion = await self._llm.ainvoke(
                    messages=[c.message for c in completions],
                    model=model,
                    reasoning_effort=reasoning_effort,
                    tools=tools,
                )
                completions.append(completion)
                yield completions

            latest_completion = completions[-1]
            match latest_completion.finish_reason:
                case "stop" | "length":
                    break
                case "tool_calls":
                    tool_calls = latest_completion.message.tool_calls
                    if not tool_calls:
                        break
                    async for tool_message in self._exec_tool_calls(
                        tool_calls=tool_calls,
                        tool_manager=tm,
                    ):
                        completions.append(Completion(message=tool_message))
                        yield completions

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, _, __, ___) -> Self:
        await self.close()
        return self

    async def close(self) -> None:
        await self._llm.close()
