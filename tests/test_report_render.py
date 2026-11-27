import re
from datetime import date

import pytest

from papertrail.models import (
    Check,
    CheckInput,
    CheckStatus,
    Claim,
    ClaimType,
    Evidence,
    Explanation,
    InputKind,
    SourceQuality,
    SourceType,
    Stance,
    Verdict,
    VerdictLabel,
)
from papertrail.report.render import md_escape, render, safe_url
from tests.test_report_builder import completed_check

ATTACK = "<script>alert(1)</script> [click](javascript:alert(2)) ![x](https://evil.test/i.png)"


def hostile_check() -> Check:
    claim = Claim(
        id="clm_1",
        text=f"Claim {ATTACK}",
        quote=f"यह स्टॉक 300% देगा {ATTACK}",
        claim_type=ClaimType.PAST_PERFORMANCE,
    )
    ev = Evidence(
        id="evd_x_1",
        claim_id="clm_1",
        url="https://news.example.com/a",
        title=f"Title {ATTACK}",
        source_type=SourceType.REPUTABLE_NEWS,
        snippet=f"Snippet {ATTACK}",
        stance=Stance.CONTEXT,
        quality=SourceQuality(reliability=0.8, recency=0.5, relevance=0.5),
        published_at=date(2025, 1, 1),
    )
    verdict = Verdict(
        claim_id="clm_1",
        label=VerdictLabel.NOT_VERIFIABLE,
        confidence=0.3,
        context_evidence_ids=["evd_x_1"],
        explanation=Explanation(
            summary=f"Summary {ATTACK}", reasoning=["See evd_x_1 for context."]
        ),
    )
    return Check(
        input=CheckInput(kind=InputKind.TEXT, text="x y z", creator_handle="@demo"),
        status=CheckStatus.COMPLETED,
        claims=[claim],
        evidence=[ev],
        verdicts=[verdict],
    )


def test_html_report_contains_everything_and_is_print_ready():
    html = render(completed_check(), "html")
    for expected in (
        "PaperTrail · Fact-check report",
        "Claims and verdicts",
        "SEBI rulebook",
        "Official SEBI sources",
        "PR No. 22/2025",
        "not financial advice",
        "@page",
        "Save as PDF / Print",
        "Method and limitations",
    ):
        assert expected in html
    assert "window.print()" in html and "addEventListener('load'" not in html
    assert "addEventListener('load'" in render(completed_check(), "html", auto_print=True)


def test_html_escapes_untrusted_text_and_keeps_hindi():
    html = render(hostile_check(), "html")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert 'href="javascript:' not in html
    assert "यह स्टॉक 300% देगा" in html
    assert "See [1] for context." in html  # internal id replaced with the citation number


def test_markdown_escapes_untrusted_text():
    md = render(hostile_check(), "md")
    # Every special character from untrusted text is backslash-escaped, so nothing can become
    # a link, image or HTML tag.
    assert not re.search(r"(?<!\\)<script", md)
    assert not re.search(r"(?<!\\)\]\(javascript:", md)
    assert not re.search(r"(?<!\\)!(?<!\\)\[x", md)
    assert "\\<script\\>" in md and "\\[click\\]" in md
    assert "यह स्टॉक 300% देगा" in md
    assert "[1] [Title" in md and "(<https://news.example.com/a>)" in md


def test_markdown_report_structure():
    md = render(completed_check(), "md")
    assert md.startswith("# PaperTrail fact-check report")
    assert "## Claims and verdicts" in md and "## SEBI rulebook" in md
    assert "**Verdict: Misleading**" in md and "\n\n\n" not in md


def test_helpers():
    assert md_escape("a*b_c\nd") == "a\\*b\\_c d"
    assert safe_url("https://x.test") == "https://x.test" and safe_url("javascript:x") == "#"
    with pytest.raises(ValueError):
        render(completed_check(), "pdf")
