import logging
from collections import defaultdict
from typing import Literal

from anyio import Path
from companion_core import AnyMessage
from pydantic import Secret, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


db: dict[int, list[AnyMessage]] = defaultdict(list)


class Config(BaseSettings):
    tg_owner_id: Secret[int]
    tg_bot_token: SecretStr
    tg_bot_proxy: SecretStr | None = None
    llm_model: str = "qwen3.5:4b"
    llm_reasoning_effort: Literal["none", "low", "high", "max"] | None = None
    stt_model_size: Literal["small", "medium", "large"] = "medium"
    stt_models_dir: Path = Path("stt/models")
    stt_device: Literal["auto", "cpu", "gpu"] = "auto"
    hf_access_token: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
