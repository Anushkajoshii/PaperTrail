"""Uploaded files. Local disk now, S3 later.

Safety: the client never chooses the storage path. Keys are random, only known file types are
accepted, and sizes are capped. Text uploads (subtitles/transcripts) must be UTF-8.
"""

from __future__ import annotations

import uuid
from pathlib import Path, PurePath
from typing import Protocol

from papertrail.tools.transcribe import SUPPORTED_MEDIA, SUPPORTED_TEXT

TEXT_MAX_BYTES = 1_000_000


class UploadError(ValueError):
    pass


class UploadStorage(Protocol):
    def save(self, filename: str, data: bytes) -> str: ...
    def read_text(self, key: str) -> str: ...


def safe_extension(filename: str) -> str:
    ext = PurePath(filename).suffix.lower().lstrip(".")
    if ext not in SUPPORTED_MEDIA and ext not in SUPPORTED_TEXT:
        allowed = ", ".join(sorted({*SUPPORTED_MEDIA, *SUPPORTED_TEXT}))
        raise UploadError(f"File type '.{ext}' is not supported. Allowed: {allowed}")
    return ext


def is_text_upload(key: str) -> bool:
    return PurePath(key).suffix.lower().lstrip(".") in SUPPORTED_TEXT


class LocalUploadStorage:
    def __init__(self, directory: str | Path, *, max_bytes: int = 25_000_000) -> None:
        self._dir = Path(directory)
        self._max = max_bytes
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, data: bytes) -> str:
        ext = safe_extension(filename)
        limit = TEXT_MAX_BYTES if ext in SUPPORTED_TEXT else self._max
        if not data:
            raise UploadError("The file is empty")
        if len(data) > limit:
            raise UploadError(f"The file is larger than the {limit // 1_000_000} MB limit")
        if ext in SUPPORTED_TEXT:
            try:
                data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise UploadError("Text files must be UTF-8 encoded") from exc
        key = f"uploads/{uuid.uuid4().hex}.{ext}"
        (self._dir / Path(key).name).write_bytes(data)
        return key

    def read_text(self, key: str) -> str:
        name = Path(key).name  # never trust a path; only the generated file name is used
        return (self._dir / name).read_text(encoding="utf-8")
