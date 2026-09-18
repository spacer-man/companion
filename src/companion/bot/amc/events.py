from typing import Annotated, Literal

from companion_core import AnyMessage
from pydantic import BaseModel, Field


class AudioTranscribingStart(BaseModel):
    type: Literal["audio.transcribing.start"] = "audio.transcribing.start"


class AudioTranscribingDone(BaseModel):
    type: Literal["audio.transcribing.done"] = "audio.transcribing.done"
    transcribed: str | None


class ComposeDone(BaseModel):
    type: Literal["done"] = "done"
    message: AnyMessage


ComposeEventData = Annotated[
    AudioTranscribingStart | AudioTranscribingDone | ComposeDone,
    Field(discriminator="type"),
]


class MessageComposeEvent(BaseModel):
    data: ComposeEventData
