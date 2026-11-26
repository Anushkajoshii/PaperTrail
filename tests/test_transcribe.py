import io
import json

import pytest

from papertrail.config import Settings
from papertrail.models import Language
from papertrail.tools.transcribe import (
    AwsTranscriber,
    TranscriptionError,
    media_format_for,
    parse_subtitles,
    parse_transcribe_output,
    transcript_from_text_file,
)

SRT = """1
00:00:01,000 --> 00:00:04,500
Namaste doston,

2
00:00:04,500 --> 00:00:09,000
<i>is stock ne</i> pichle saal 300% return diya.
"""

VTT = """WEBVTT

NOTE made by hand

00:01.000 --> 00:03.000
Nifty hit 26,000 today.

00:01:03.250 --> 00:01:05.000 align:start
Buy before Monday.
"""


def test_parse_srt():
    segs = parse_subtitles(SRT)
    assert [(s.start_seconds, s.end_seconds) for s in segs] == [(1.0, 4.5), (4.5, 9.0)]
    assert segs[1].text == "is stock ne pichle saal 300% return diya."  # tags removed


def test_parse_vtt_with_header_notes_and_settings():
    segs = parse_subtitles(VTT)
    assert [s.text for s in segs] == ["Nifty hit 26,000 today.", "Buy before Monday."]
    assert segs[1].start_seconds == pytest.approx(63.25)


def test_text_file_transcripts():
    t = transcript_from_text_file("clip.srt", SRT)
    assert t.source == "subtitle_file" and t.language is Language.HINGLISH
    assert t.text.startswith("Namaste doston")
    plain = transcript_from_text_file("post.TXT", "  Nifty is at 24,000.  ")
    assert plain.text == "Nifty is at 24,000." and plain.segments == []
    with pytest.raises(TranscriptionError, match="Unsupported"):
        transcript_from_text_file("deck.pdf", "x")
    with pytest.raises(TranscriptionError, match="No captions"):
        transcript_from_text_file("empty.vtt", "WEBVTT\n")


def test_media_format():
    assert media_format_for("uploads/abc/Clip.MP4") == "mp4"
    with pytest.raises(TranscriptionError, match="Supported"):
        media_format_for("uploads/x.mov")


TRANSCRIBE_JSON = {
    "results": {
        "language_code": "hi-IN",
        "transcripts": [{"transcript": "यह शेयर बढ़ेगा। अभी खरीदें।"}],
        "audio_segments": [
            {"transcript": "यह शेयर बढ़ेगा।", "start_time": "0.5", "end_time": "2.1"},
            {"transcript": "अभी खरीदें।", "start_time": "2.1", "end_time": "3.0"},
        ],
    }
}


def test_parse_transcribe_output_with_audio_segments():
    t = parse_transcribe_output(TRANSCRIBE_JSON)
    assert t.language is Language.HINDI and t.detected_language_code == "hi-IN"
    assert [s.start_seconds for s in t.segments] == [0.5, 2.1]


def test_parse_transcribe_output_from_items():
    data = {
        "results": {
            "transcripts": [{"transcript": "Buy now. Target 500"}],
            "items": [
                {
                    "type": "pronunciation",
                    "start_time": "0.0",
                    "end_time": "0.3",
                    "alternatives": [{"content": "Buy"}],
                },
                {
                    "type": "pronunciation",
                    "start_time": "0.3",
                    "end_time": "0.6",
                    "alternatives": [{"content": "now"}],
                },
                {"type": "punctuation", "alternatives": [{"content": "."}]},
                {
                    "type": "pronunciation",
                    "start_time": "1.0",
                    "end_time": "1.4",
                    "alternatives": [{"content": "Target"}],
                },
                {
                    "type": "pronunciation",
                    "start_time": "1.4",
                    "end_time": "1.9",
                    "alternatives": [{"content": "500"}],
                },
            ],
        }
    }
    segs = parse_transcribe_output(data).segments
    assert [(s.text, s.start_seconds) for s in segs] == [("Buy now.", 0.0), ("Target 500", 1.0)]


class FakeTranscribe:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.started = None

    def start_transcription_job(self, **kwargs):
        self.started = kwargs

    def get_transcription_job(self, TranscriptionJobName):
        status = self.statuses.pop(0)
        job = {"TranscriptionJobStatus": status}
        if status == "FAILED":
            job["FailureReason"] = "bad audio"
        return {"TranscriptionJob": job}


class FakeS3:
    def __init__(self):
        self.requested = None

    def get_object(self, Bucket, Key):
        self.requested = (Bucket, Key)
        return {"Body": io.BytesIO(json.dumps(TRANSCRIBE_JSON).encode())}


def test_aws_transcriber_happy_path():
    tr, s3 = FakeTranscribe(["IN_PROGRESS", "IN_PROGRESS", "COMPLETED"]), FakeS3()
    sleeps = []
    t = AwsTranscriber(tr, s3, "pt-media", poll_seconds=2, sleep=sleeps.append).transcribe(
        "uploads/1/clip.mp4"
    )
    assert t.language is Language.HINDI and sleeps == [2, 2]
    req = tr.started
    assert req["Media"]["MediaFileUri"] == "s3://pt-media/uploads/1/clip.mp4"
    assert req["IdentifyLanguage"] is True and req["LanguageOptions"] == ["en-IN", "hi-IN"]
    assert {"Key": "project", "Value": "papertrail"} in req["Tags"]
    assert s3.requested == ("pt-media", f"transcripts/{req['TranscriptionJobName']}.json")


def test_aws_transcriber_failure_and_timeout():
    with pytest.raises(TranscriptionError, match="bad audio"):
        AwsTranscriber(FakeTranscribe(["FAILED"]), FakeS3(), "b", sleep=lambda s: None).wait("j")
    slow = AwsTranscriber(
        FakeTranscribe(["IN_PROGRESS"] * 5),
        FakeS3(),
        "b",
        poll_seconds=1,
        timeout_seconds=2,
        sleep=lambda s: None,
    )
    with pytest.raises(TranscriptionError, match="did not finish"):
        slow.wait("j")


def test_transcriber_without_bucket_explains_local_alternative():
    with pytest.raises(TranscriptionError, match=r"\.srt/\.vtt/\.txt"):
        AwsTranscriber.from_settings(Settings(_env_file=None))
