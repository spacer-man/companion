from pathlib import Path
from typing import Literal, Self

from agents.mcp import MCPServerStdioParams
from pydantic import BaseModel, Field, HttpUrl, Secret, SecretStr

# =====================================================
# =                        MCP                        =
# =====================================================


class MCPServerStdioConfig(BaseModel):
    name: str
    params: MCPServerStdioParams
    cache_tools_list: bool = True


class MCPServersConfig(BaseModel):
    active: bool = True
    servers: list[MCPServerStdioConfig] = Field(default_factory=list)


# =====================================================
# =                        LLM                        =
# =====================================================


class LLMConfig(BaseModel):
    model: str
    reasoning_effort: Literal["none", "low", "high", "max"] | None = None
    api_key: SecretStr | None = None
    base_url: HttpUrl | None = None


# =====================================================
# =                        STT                        =
# =====================================================


class BaseSTTConfig(BaseModel):
    active: bool = False


class WhisperSTTConfig(BaseSTTConfig):
    provider: Literal["whisper"] = "whisper"
    model_size: Literal["small", "medium", "large"] = "medium"
    models_dir: Path = Path("stt")
    device: Literal["auto", "cpu", "gpu"] = "auto"
    hf_access_token: SecretStr | None = None


type STTConfig = WhisperSTTConfig  # Later maybe add Field(discriminator="provider")


# =====================================================
# =                     Telegram                      =
# =====================================================


class PersonalChatConfig(BaseModel):
    send_audio_transcribtion: bool = True


class TelegramConfig(BaseModel):
    owner_ids: list[Secret[int]]
    bot_token: SecretStr
    bot_proxy_url: SecretStr | None = None
    personal: PersonalChatConfig = Field(default_factory=PersonalChatConfig)


# =====================================================
# =                     Database                      =
# =====================================================


class SqliteDBConfig(BaseModel):
    provider: Literal["sqlite"] = "sqlite"
    db_path: str | Path = ":memory:"


type DBConfig = SqliteDBConfig


# =====================================================
# =                   Full config                     =
# =====================================================


class AgentConfig(BaseModel):
    telegram: TelegramConfig
    llm: LLMConfig
    db: DBConfig = Field(default_factory=DBConfig)
    stt: STTConfig | None = None
    mcp: MCPServersConfig | None = None

    @classmethod
    def load(cls, filepath: str | Path) -> Self:
        raw_config = Path(filepath).read_text()

        return cls.model_validate_json(raw_config)
