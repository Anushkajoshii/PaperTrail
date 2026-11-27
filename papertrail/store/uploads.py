"""Uploaded files: local disk for development, Amazon S3 in AWS.

Safety: the client never chooses the storage path. Keys are random, only known file types are
accepted, and sizes are capped. Text uploads (subtitles/transcripts) must be UTF-8.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path, PurePath
from typing import Any, Protocol

from papertrail.tools.transcribe import SUPPORTED_MEDIA, SUPPORTED_TEXT

TEXT_MAX_BYTES = 1_000_000
_KEY = re.compile(r"^uploads/[0-9a-f]{32}\.[a-z0-9]{2,4}$")


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


def new_upload_key(filename: str, data: bytes, max_bytes: int) -> str:
    """Validate an upload and return a fresh random key for it (never the client's name)."""
    ext = safe_extension(filename)
    limit = TEXT_MAX_BYTES if ext in SUPPORTED_TEXT else max_bytes
    if not data:
        raise UploadError("The file is empty")
    if len(data) > limit:
        raise UploadError(f"The file is larger than the {limit / 1_000_000:g} MB limit")
    if ext in SUPPORTED_TEXT:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UploadError("Text files must be UTF-8 encoded") from exc
    return f"uploads/{uuid.uuid4().hex}.{ext}"


def is_text_upload(key: str) -> bool:
    return PurePath(key).suffix.lower().lstrip(".") in SUPPORTED_TEXT


class LocalUploadStorage:
    def __init__(self, directory: str | Path, *, max_bytes: int = 25_000_000) -> None:
        self._dir = Path(directory)
        self._max = max_bytes
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, data: bytes) -> str:
        key = new_upload_key(filename, data, self._max)
        (self._dir / Path(key).name).write_bytes(data)
        return key

    def read_text(self, key: str) -> str:
        name = Path(key).name  # never trust a path; only the generated file name is used
        return (self._dir / name).read_text(encoding="utf-8")


class S3UploadStorage:
    """Uploads in a private, encrypted S3 bucket (Amazon Transcribe reads media from here)."""

    def __init__(self, s3_client: Any, bucket: str, *, max_bytes: int = 25_000_000) -> None:
        self._s3, self._bucket, self._max = s3_client, bucket, max_bytes

    def save(self, filename: str, data: bytes) -> str:
        key = new_upload_key(filename, data, self._max)
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=data)
        return key

    def read_text(self, key: str) -> str:
        if not _KEY.match(key):
            raise UploadError("Unknown upload")
        obj = self._s3.get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read().decode("utf-8")


def get_upload_storage(settings) -> UploadStorage:
    if settings.upload_backend == "s3":
        if not settings.media_bucket:
            raise ValueError("upload_backend 's3' needs PAPERTRAIL_MEDIA_BUCKET")
        import boto3

        s3 = boto3.client("s3", region_name=settings.aws_region)
        return S3UploadStorage(s3, settings.media_bucket, max_bytes=settings.max_upload_bytes)
    return LocalUploadStorage(settings.upload_dir, max_bytes=settings.max_upload_bytes)
