from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from agents.mcp import MCPServer, MCPServerStdio

GCAL_DEFAULT_AUTH_CREDS_FILEPATH = "google_calendar_token.json"


@asynccontextmanager
async def gcal_mcp_context(creds_file: str | None = None) -> AsyncGenerator[MCPServer]:
    if not creds_file:
        creds_file = GCAL_DEFAULT_AUTH_CREDS_FILEPATH

    async with MCPServerStdio(
        name="Google Calendar",
        params={
            "command": "npx",
            "args": ["@cocal/google-calendar-mcp"],
            "env": {"GOOGLE_OAUTH_CREDENTIALS": creds_file},
        },
        cache_tools_list=True,  # avoids re-listing tools every run
    ) as calendar_server:
        yield calendar_server
