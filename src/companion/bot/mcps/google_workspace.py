from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from agents.mcp import MCPServer, MCPServerStdio
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class GoogleWorkspaceConfig(BaseSettings):
    google_oauth_client_id: SecretStr
    google_oauth_client_secret: SecretStr
    google_oauth_redirect_uri: str = "http://localhost:8000/oauth2callback"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@asynccontextmanager
async def google_workspace_mcp(
    config: GoogleWorkspaceConfig | None = None,
) -> AsyncGenerator[MCPServer]:
    if not config:
        config = GoogleWorkspaceConfig()

    async with MCPServerStdio(
        name="Google Workspace",
        params={
            "command": "uvx",
            "args": [
                "workspace-mcp",
                "--single-user",
                "--tools",
                "calendar",
                "tasks",
                "gmail",
            ],
            "env": {
                "GOOGLE_OAUTH_CLIENT_ID": config.google_oauth_client_id.get_secret_value(),
                "GOOGLE_OAUTH_CLIENT_SECRET": config.google_oauth_client_secret.get_secret_value(),
                "GOOGLE_OAUTH_REDIRECT_URI": config.google_oauth_redirect_uri,
            },
        },
        cache_tools_list=True,  # avoids re-listing tools every run
    ) as calendar_server:
        yield calendar_server
