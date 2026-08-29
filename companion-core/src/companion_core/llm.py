from collections.abc import AsyncGenerator, Iterable
from typing import Literal

from openai import AsyncClient
from openai.types.chat import (
    ChatCompletionCustomToolParam,
    ChatCompletionFunctionToolParam,
    ChatCompletionMessageCustomToolCall,
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionMessageParam,
)

from companion_core.tools import FuncTool
from companion_core.types import (
    AiMessage,
    AnyMessage,
    Completion,
    ToolCall,
    ToolFunction,
)


class LLM:
    def __init__(
        self,
        base_url: str,
        api_key: str,
    ) -> None:
        self._client = AsyncClient(base_url=base_url, api_key=api_key)

    def _dump_messages(
        self,
        messages: Iterable[AnyMessage],
        /,
    ) -> Iterable[ChatCompletionMessageParam]:
        def messages_dumped_generator():
            for message in messages:
                input_images: list[str] | None = getattr(message, "images", None)
                if input_images:
                    content = []
                    if message.content:
                        content.append({"type": "text", "text": message.content})
                    for image in input_images:
                        content.append({"type": "image_url", "image_url": image})
                else:
                    content = message.content
                yield {"role": message.role, "content": content}

        return messages_dumped_generator()

    def _extract_tool_shemas(
        self,
        tools: Iterable[FuncTool] | None,
        /,
    ) -> Iterable[ChatCompletionFunctionToolParam | ChatCompletionCustomToolParam]:
        return [tool.tool_schema for tool in tools or []]

    def _parse_tool_calls(
        self,
        tool_calls: list[
            ChatCompletionMessageFunctionToolCall | ChatCompletionMessageCustomToolCall
        ]
        | None,
    ) -> list[ToolCall] | None:
        parsed_tool_calls = []
        for tool_call in tool_calls or []:
            if tool_call.type == "function":
                parsed_tool_calls.append(
                    ToolCall(
                        id=tool_call.id,
                        type=tool_call.type,
                        function=ToolFunction(
                            name=tool_call.function.name,
                            arguments=tool_call.function.arguments,
                        ),
                    )
                )
        return parsed_tool_calls or None

    async def ainvoke(
        self,
        messages: Iterable[AnyMessage],
        model: str,
        reasoning_effort: Literal["none", "low", "high", "max"] | None = None,
        tools: Iterable[FuncTool] | None = None,
    ) -> Completion[AiMessage]:
        raw_completion = await self._client.chat.completions.create(
            messages=self._dump_messages(messages),
            model=model,
            tools=self._extract_tool_shemas(tools),
            reasoning_effort=reasoning_effort,
        )
        raw_choice = raw_completion.choices[0]
        return Completion(
            message=AiMessage(
                content=raw_choice.message.content or "",
                reasoning=getattr(raw_choice.message, "reasoning", None),
                tool_calls=self._parse_tool_calls(raw_choice.message.tool_calls),
            ),
            finish_reason=raw_choice.finish_reason,
        )

    async def astream(
        self,
        messages: Iterable[AnyMessage],
        model: str,
        reasoning_effort: Literal["none", "low", "high", "max"] | None = None,
        tools: Iterable[FuncTool] | None = None,
    ) -> AsyncGenerator[Completion[AiMessage]]:
        async with self._client.chat.completions.stream(
            messages=self._dump_messages(messages),
            tools=self._extract_tool_shemas(tools),
            model=model,
            reasoning_effort=reasoning_effort,
        ) as stream:
            last_completion = Completion(message=AiMessage(content=""))
            tool_calls: list[ToolCall] = []
            async for event in stream:
                if event.type == "chunk":
                    current_chunk = event.chunk.choices[0].delta.content
                    delta_tool_calls = event.chunk.choices[0].delta.tool_calls
                    tool_calls.extend(self._parse_tool_calls(delta_tool_calls) or [])  # ty: ignore[invalid-argument-type]
                    choice = event.snapshot.choices[0]
                    message = choice.message
                    last_completion = Completion(
                        message=AiMessage(
                            content=message.content,
                            reasoning=getattr(message, "reasoning", None),
                            tool_calls=tool_calls or None,
                        ),
                        current_chunk=current_chunk,
                        finish_reason=choice.finish_reason,
                    )
                yield last_completion

    async def close(self) -> None:
        await self._client.close()
