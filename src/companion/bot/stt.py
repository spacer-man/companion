from io import BytesIO
from typing import Protocol

from faster_whisper import WhisperModel


class STT(Protocol):
    """Base STT interface."""

    async def transcribe(self, audio: BytesIO) -> str:
        """Transcribe audio."""
        ...


class WhisperSTT(STT):
    """Whisper STT implementation."""

    def __init__(self, model: WhisperModel) -> None:
        self._model = model

    async def transcribe(self, audio: BytesIO) -> str:
        segments, _info = self._model.transcribe(
            audio=audio,
            multilingual=True,
            vad_filter=True,
        )

        transcribed = "".join(segment.text for segment in segments).strip()
        return transcribed
