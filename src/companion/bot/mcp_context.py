from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from agents.mcp import MCPServer, MCPServerManager, MCPServerStdio

from companion.bot.config import MCPServersConfig


@asynccontextmanager
async def mcp_context(
    config: MCPServersConfig | None = None,
) -> AsyncGenerator[list[MCPServer]]:
    if not config or not config.active:
        yield []
    else:
        async with MCPServerManager(
            servers=[
                MCPServerStdio(
                    name=s.name,
                    params=s.params,
                    cache_tools_list=s.cache_tools_list,
                )
                for s in config.servers
            ]
        ) as mcp_manager:
            yield mcp_manager.active_servers
