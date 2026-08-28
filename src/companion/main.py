import asyncio

from companion_core import LLM, Agent, UserMessage, tool


@tool
def get_weather(city: str) -> str:
    return f"It's sunny in {city.title()} now."


async def run() -> None:
    async with Agent(
        llm=LLM(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
        ),
        tool_call_error_ok=True,
    ) as agent:
        async for completions in agent.astream(
            messages=[UserMessage(content=input(">>> "))],
            model="qwen3.5:4b",
            reasoning_effort="low",
            tools=[get_weather],
        ):
            print(completions[-1].message)


if __name__ == "__main__":
    asyncio.run(run())
