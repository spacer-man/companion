import asyncio
import base64
import json
import logging
from io import BytesIO
from typing import Any, Literal

import pyvips
from aiogram import Bot
from aiogram.types import Audio, Document, PhotoSize, Sticker, Voice
from aiogram.types import Message as AiogramMessage
from companion_core.types import AnyMessage, Message

from companion.bot.stt import STT

from .abc import AgentMessageComposer

log = logging.getLogger(__name__)


UNKNOWN_FIELD_DEFAULT_VALUE = "<unknown>"
DATETIME_STRING_FORMAT = "%d.%m.%YT%H:%MZ%z"
IMAGE_FILE_EXTENTIONS = ("png", "jpg", "jpeg")
DEFAULT_IMAGE_FILE_EXTENTION = "jpg"


class AiogramAMC(AgentMessageComposer[AiogramMessage]):
    """The aiogram Agent message composer implementation."""

    def __init__(self, bot: Bot, stt: STT | None = None) -> None:
        self._bot = bot
        self._stt = stt

    async def _pull_image(self, image: PhotoSize | Sticker | Document) -> str:
        """Download image and return url with it encoded to base64."""
        log.debug(f"Poolling image: {image!r}")
        image_data = BytesIO()
        image_file, _ = await asyncio.gather(
            self._bot.get_file(file_id=image.file_id),
            self._bot.download(file=image, destination=image_data),
        )
        log.debug(f"Poolled image file: {image_file!r}")
        file_extention = (
            image_file.file_path.split(".")[-1].lower()
            if image_file.file_path
            else DEFAULT_IMAGE_FILE_EXTENTION
        )

        # Convert file to default file extention if it needed
        if file_extention not in IMAGE_FILE_EXTENTIONS:
            file_extention = DEFAULT_IMAGE_FILE_EXTENTION
            pyvips_image = pyvips.Image.new_from_buffer(image_data.getvalue(), "")
            image_data = BytesIO(pyvips_image.write_to_buffer("." + file_extention))

        # Encode to base64
        image_base64 = base64.b64encode(image_data.getvalue()).decode("utf-8")
        image_url = f"data:image/{file_extention};base64,{image_base64}"
        log.debug(f"Result base64 image url: {image_url[:40]!r}")
        return image_url

    async def _pull_audio(self, audio: Audio | Voice | Document) -> str | None:
        if not self._stt:
            return None

        audio_data = BytesIO()
        await self._bot.download(file=audio, destination=audio_data)

        transcribed = await self._stt.transcribe(
            audio=audio_data,
        )

        return transcribed

    async def compose(
        self,
        message: AiogramMessage,
        role: Literal["assistant", "user"],
    ) -> AnyMessage:
        # ====== Serialize content ======
        content_data: dict[str, Any] = {
            "id": message.message_id,
            "text": message.text or message.caption,
            "voice": (await self._pull_audio(message.voice) if message.voice else None),
            "audio": (await self._pull_audio(message.audio) if message.audio else None),
            "type": "sticker" if message.sticker else None,
            "date": message.date.strftime(DATETIME_STRING_FORMAT),
            "author": (
                message.from_user.full_name
                if message.from_user
                else UNKNOWN_FIELD_DEFAULT_VALUE
            ),
        }
        content: str = json.dumps(
            {k: v for k, v in content_data.items() if v is not None}
        )

        # ====== Pull images ======
        images: list[str] = []

        if message.photo:
            images.append(await self._pull_image(message.photo[0]))
        elif message.sticker and not message.sticker.is_animated:
            if message.sticker.thumbnail:
                images.append(await self._pull_image(message.sticker.thumbnail))
            else:
                images.append(await self._pull_image(message.sticker))
        elif (  # If message has a image document
            message.document
            and message.document.file_name
            and any(
                message.document.file_name.lower().endswith("." + extention.lower())
                for extention in IMAGE_FILE_EXTENTIONS
            )
        ):
            images.append(await self._pull_image(message.document))

        # ====== Compose all to a message ======
        return Message(
            content=content,
            role=role,
            images=images,
        )
