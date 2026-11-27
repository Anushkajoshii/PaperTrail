"""Render a Report as HTML (print-ready, "Save as PDF" in any browser) or Markdown.

Report text includes untrusted content (creators' words, web page snippets and titles), so:
* HTML uses Jinja2 autoescaping, and links must be http(s) (no ``javascript:`` URLs);
* Markdown escapes the characters that could create links, images, HTML or formatting.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from papertrail.models import Check
from papertrail.report.builder import Report, build_report

TEMPLATES = Path(__file__).parent / "templates"

_MD_SPECIAL = re.compile(r"([\\`*_\[\]{}<>#|!~])")


def md_escape(value: object) -> str:
    text = " ".join(str(value).split())  # no newlines: keeps untrusted text inside its line
    return _MD_SPECIAL.sub(r"\\\1", text)


def safe_url(value: object) -> str:
    url = str(value)
    return url if urlparse(url).scheme in {"http", "https"} else "#"


def _env(autoescape: bool) -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        # Explicit on/off: select_autoescape() decides by file extension, and ".html.j2" does
        # not end in ".html", so it would silently leave HTML unescaped.
        autoescape=autoescape,
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    env.filters["md"] = md_escape
    env.filters["safe_url"] = safe_url
    return env


_HTML = _env(autoescape=True)
_MD = _env(autoescape=False)


def render_html(report: Report, *, auto_print: bool = False) -> str:
    return _HTML.get_template("report.html.j2").render(r=report, auto_print=auto_print)


def render_markdown(report: Report) -> str:
    text = _MD.get_template("report.md.j2").render(r=report)
    return re.sub(r"\n{3,}", "\n\n", text)


def render(check: Check, fmt: str = "html", *, auto_print: bool = False) -> str:
    report = build_report(check)
    if fmt == "html":
        return render_html(report, auto_print=auto_print)
    if fmt == "md":
        return render_markdown(report)
    raise ValueError(f"Unknown report format '{fmt}'")
