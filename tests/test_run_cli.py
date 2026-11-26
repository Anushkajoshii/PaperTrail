import json
from pathlib import Path

import pytest

from papertrail.agent import run as run_cli
from papertrail.agent.graph import AgentDeps
from papertrail.config import Settings
from papertrail.llm import MockProvider
from papertrail.tools.search import OfflineSearch

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def fake_from_settings(settings=None, **overrides):
        base = dict(
            provider=MockProvider(),
            search=OfflineSearch(),
            fetcher=None,
            registry=None,
            settings=Settings(_env_file=None),
        )
        return AgentDeps(**(base | overrides))

    monkeypatch.setattr(run_cli.AgentDeps, "from_settings", staticmethod(fake_from_settings))


def test_readable_report(capsys):
    assert run_cli.main([str(EXAMPLES / "english_post.txt")]) == 0
    out = capsys.readouterr().out
    assert "✅ Supported" in out and "❌ Contradicted" in out and "❔ Not verifiable" in out
    assert "Why:" in out and "not financial advice" in out and "Run:" in out


def test_json_output_and_flags(capsys):
    assert run_cli.main([str(EXAMPLES / "hinglish_reel.txt"), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "completed" and len(data["claims"]) == 4
    assert {f["basis"] for f in data["red_flags"]} == {"verified_rule"}


def test_subtitle_file_and_failure_exit_code(tmp_path, capsys):
    srt = tmp_path / "clip.srt"
    srt.write_text("1\n00:00:02,000 --> 00:00:04,000\nGuaranteed 10% every month, risk-free.\n")
    assert run_cli.main([str(srt)]) == 0
    assert "OFFICIAL" in capsys.readouterr().out
    empty = tmp_path / "empty.txt"
    empty.write_text("   ")
    assert run_cli.main([str(empty)]) == 1
    assert "Check failed" in capsys.readouterr().out
