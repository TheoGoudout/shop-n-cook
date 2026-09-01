"""Validation of user-supplied recipe photos.

Photos are transient: they are validated, handed to the vision model and then
dropped. Nothing is written to disk or to the database.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.core.config import settings
from app.services.recipe_import.errors import InvalidPhotoError

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
RIFF_MAGIC = b"RIFF"
WEBP_MAGIC = b"WEBP"


@dataclass(frozen=True)
class PhotoInput:
    """One validated image, ready to be base64-encoded into a model request."""

    data: bytes
    media_type: str


def sniff_media_type(data: bytes) -> str | None:
    """Return the media type implied by the leading bytes, or None if unknown.

    The client-declared content type is never trusted — a renamed text file
    would sail past it and be billed as a vision request.
    """
    if data.startswith(JPEG_MAGIC):
        return "image/jpeg"
    if data.startswith(PNG_MAGIC):
        return "image/png"
    if len(data) >= 12 and data.startswith(RIFF_MAGIC) and data[8:12] == WEBP_MAGIC:
        return "image/webp"
    return None


def validate_photos(raw: Sequence[bytes]) -> list[PhotoInput]:
    """Check count, size and real format of the uploaded photos.

    Raises:
        InvalidPhotoError: if the batch is empty, too large, or not all images.
    """
    if not raw:
        raise InvalidPhotoError("At least one photo is required")
    if len(raw) > settings.RECIPE_PHOTO_MAX_COUNT:
        raise InvalidPhotoError(
            f"At most {settings.RECIPE_PHOTO_MAX_COUNT} photos can be imported at once"
        )

    photos: list[PhotoInput] = []
    for index, data in enumerate(raw):
        if not data:
            raise InvalidPhotoError(f"Photo {index + 1} is empty")
        if len(data) > settings.RECIPE_PHOTO_MAX_BYTES:
            raise InvalidPhotoError(
                f"Photo {index + 1} exceeds the "
                f"{settings.RECIPE_PHOTO_MAX_BYTES} byte limit"
            )
        media_type = sniff_media_type(data)
        if media_type is None:
            raise InvalidPhotoError(
                f"Photo {index + 1} is not a JPEG, PNG or WebP image"
            )
        photos.append(PhotoInput(data=data, media_type=media_type))
    return photos
