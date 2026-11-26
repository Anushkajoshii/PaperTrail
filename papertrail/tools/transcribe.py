"""Turn uploaded media into a timed transcript.

Two paths:

* **Amazon Transcribe** (cloud): audio/video in S3 is transcribed with automatic language
  identification between Indian English (``en-IN``) and Hindi (``hi-IN``). Used by the worker.
* **Subtitle or text files** (local, no AWS): ``.srt``, ``.vtt`` or ``.txt``. Useful for
  development, and for users who already have captions.

Media is never downloaded from YouTube or Instagram (see ADR-001).
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any

from papertrail.models import Language, TranscriptSegment
from papertrail.text import detect_language

SUPPORTED_MEDIA = {
    "mp3": "mp3",
    "mp4": "mp4",
    "m4a": "m4a",
    "wav": "wav",
    "flac": "flac",
    "ogg": "ogg",
    "webm": "webm",
    "amr": "amr",
}
SUPPORTED_TEXT = {"srt", "vtt", "txt"}
TRANSCRIBE_LANGUAGES = ["en-IN", "hi-IN"]


class TranscriptionError(RuntimeError):
    pass


@dataclass
class Transcript:
    text: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: Language = Language.ENGLISH
    source: str = "text"  # "aws_transcribe" | "subtitle_file" | "text"
    detected_language_code: str | None = None


# ------------------------------------------------------------------------------------------
# Subtitles and plain text
# ------------------------------------------------------------------------------------------

_TIMING = re.compile(
    r"(?P<s>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3})\s*-->\s*(?P<e>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3})"
)
_TAGS = re.compile(r"<[^>]+>")


def _to_seconds(stamp: str) -> float:
    parts = stamp.replace(",", ".").split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) == 3 else 0
    return hours * 3600 + minutes * 60 + seconds


def parse_subtitles(content: str) -> list[TranscriptSegment]:
    """Parse SRT or WebVTT captions into segments. Cue numbers, styling and tags are removed."""
    segments: list[TranscriptSegment] = []
    blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n").strip())
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        timing_idx = next((i for i, ln in enumerate(lines) if _TIMING.search(ln)), None)
        if timing_idx is None:
            continue  # header ("WEBVTT"), NOTE or STYLE blocks
        m = _TIMING.search(lines[timing_idx])
        text = " ".join(_TAGS.sub("", ln) for ln in lines[timing_idx + 1 :]).strip()
        if text:
            segments.append(
                TranscriptSegment(
                    start_seconds=_to_seconds(m["s"]), end_seconds=_to_seconds(m["e"]), text=text
                )
            )
    return segments


def transcript_from_text_file(filename: str, content: str) -> Transcript:
    ext = PurePath(filename).suffix.lower().lstrip(".")
    if ext not in SUPPORTED_TEXT:
        raise TranscriptionError(f"Unsupported transcript file type '.{ext}'")
    if ext == "txt":
        text = content.strip()
        return Transcript(text=text, language=detect_language(text), source="text")
    segments = parse_subtitles(content)
    if not segments:
        raise TranscriptionError("No captions found in the subtitle file")
    text = " ".join(s.text for s in segments)
    return Transcript(
        text=text, segments=segments, language=detect_language(text), source="subtitle_file"
    )


# ------------------------------------------------------------------------------------------
# Amazon Transcribe
# ------------------------------------------------------------------------------------------


def media_format_for(key: str) -> str:
    ext = PurePath(key).suffix.lower().lstrip(".")
    if ext not in SUPPORTED_MEDIA:
        raise TranscriptionError(
            f"Unsupported media type '.{ext}'. Supported: {', '.join(sorted(SUPPORTED_MEDIA))}"
        )
    return SUPPORTED_MEDIA[ext]


def parse_transcribe_output(data: dict[str, Any]) -> Transcript:
    """Parse Amazon Transcribe's JSON result into text + timed segments."""
    results = data.get("results") or {}
    transcripts = results.get("transcripts") or []
    text = " ".join(t.get("transcript", "") for t in transcripts).strip()
    segments: list[TranscriptSegment] = []
    for seg in results.get("audio_segments") or []:
        seg_text = (seg.get("transcript") or "").strip()
        if seg_text:
            segments.append(
                TranscriptSegment(
                    start_seconds=float(seg.get("start_time", 0)),
                    end_seconds=float(seg.get("end_time", 0)),
                    text=seg_text,
                )
            )
    if not segments:
        segments = _segments_from_items(results.get("items") or [])
    code = results.get("language_code")
    return Transcript(
        text=text,
        segments=segments,
        language=detect_language(text),
        source="aws_transcribe",
        detected_language_code=code,
    )


def _segments_from_items(items: list[dict[str, Any]]) -> list[TranscriptSegment]:
    """Fallback for older outputs: group word items into sentences at punctuation."""
    segments: list[TranscriptSegment] = []
    words: list[str] = []
    start = end = None
    for item in items:
        content = (item.get("alternatives") or [{}])[0].get("content", "")
        if item.get("type") == "pronunciation":
            if start is None:
                start = float(item.get("start_time", 0))
            end = float(item.get("end_time", start))
            words.append(content)
        elif item.get("type") == "punctuation" and words:
            words[-1] += content
            if content in {".", "?", "!", "।"}:
                segments.append(
                    TranscriptSegment(start_seconds=start, end_seconds=end, text=" ".join(words))
                )
                words, start, end = [], None, None
    if words:
        segments.append(
            TranscriptSegment(start_seconds=start, end_seconds=end, text=" ".join(words))
        )
    return segments


class AwsTranscriber:
    """Runs an Amazon Transcribe job for a file already in S3 and returns the transcript.

    Clients are injected (boto3 ``transcribe`` and ``s3``), so tests never touch AWS.
    """

    def __init__(
        self,
        transcribe_client: Any,
        s3_client: Any,
        bucket: str,
        *,
        poll_seconds: float = 5.0,
        timeout_seconds: float = 900.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._transcribe = transcribe_client
        self._s3 = s3_client
        self._bucket = bucket
        self._poll = poll_seconds
        self._timeout = timeout_seconds
        self._sleep = sleep

    @classmethod
    def from_settings(cls, settings: Any) -> AwsTranscriber:
        if not settings.media_bucket:
            raise TranscriptionError(
                "Audio/video transcription needs AWS (set up in Part 10). For local development, "
                "upload a .srt/.vtt/.txt transcript or paste the text instead."
            )
        import boto3

        return cls(
            boto3.client("transcribe", region_name=settings.aws_region),
            boto3.client("s3", region_name=settings.aws_region),
            settings.media_bucket,
            timeout_seconds=settings.transcribe_timeout_seconds,
        )

    def start(self, s3_key: str) -> str:
        job = f"papertrail-{uuid.uuid4().hex[:16]}"
        self._transcribe.start_transcription_job(
            TranscriptionJobName=job,
            Media={"MediaFileUri": f"s3://{self._bucket}/{s3_key}"},
            MediaFormat=media_format_for(s3_key),
            IdentifyLanguage=True,
            LanguageOptions=TRANSCRIBE_LANGUAGES,
            OutputBucketName=self._bucket,
            OutputKey=f"transcripts/{job}.json",
            Tags=[{"Key": "project", "Value": "papertrail"}],
        )
        return job

    def wait(self, job: str) -> Transcript:
        import json

        waited = 0.0
        while True:
            info = self._transcribe.get_transcription_job(TranscriptionJobName=job)
            status = info["TranscriptionJob"]["TranscriptionJobStatus"]
            if status == "COMPLETED":
                break
            if status == "FAILED":
                reason = info["TranscriptionJob"].get("FailureReason", "unknown reason")
                raise TranscriptionError(f"Transcription failed: {reason}")
            if waited >= self._timeout:
                raise TranscriptionError(f"Transcription did not finish within {self._timeout}s")
            self._sleep(self._poll)
            waited += self._poll
        obj = self._s3.get_object(Bucket=self._bucket, Key=f"transcripts/{job}.json")
        return parse_transcribe_output(json.loads(obj["Body"].read()))

    def transcribe(self, s3_key: str) -> Transcript:
        return self.wait(self.start(s3_key))
