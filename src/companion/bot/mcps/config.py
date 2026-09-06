from pathlib import Path
from typing import Literal

from agents.mcp import MCPServerStdioParams
from pydantic import BaseModel, Field, HttpUrl, Secret, SecretStr


class MCPServerStdioConfig(BaseModel):
    name: str
    params: MCPServerStdioParams
    cache_tools_list: bool = True


class MCPConfigSection(BaseModel):
    active: bool = True
    servers: list[MCPServerStdioConfig] = Field(default_factory=list)


class LLMConfig(BaseModel):
    model: str
    reasoning_effort: Literal["none", "low", "high", "max"] | None = None
    api_key: SecretStr | None = None
    base_url: HttpUrl | None = None


class WhisperConfig(BaseModel):
    model_size: Literal["small", "medium", "large"] = "medium"
    models_dir: Path = Path("stt")
    device: Literal["auto", "cpu", "gpu"] = "auto"
    hf_access_token: SecretStr | None = None


class STTConfig(BaseModel):
    active: bool = True
    service: Literal["whisper"]
    params: WhisperConfig


class TelegramConfig(BaseModel):
    owner_ids: list[Secret[int]]
    bot_token: SecretStr
    bot_proxy_url: SecretStr | None = None


class AgentConfig(BaseModel):
    telegram: TelegramConfig
    llm: LLMConfig
    mcp: MCPConfigSection | None = None
    stt: STTConfig | None = None
