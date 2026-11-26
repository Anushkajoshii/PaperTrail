"""Load and query the curated SEBI source registry (``data/sebi_sources.yaml``).

This is the *only* place a ``verified_rule`` red flag can get its citation from. Each entry is
validated by :class:`papertrail.models.RegulatorySource`, so an entry with a non-SEBI URL or
impossible dates fails at load time and in CI.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

from papertrail.models import RegulatorySource

SOURCES_PATH = Path(__file__).parent / "data" / "sebi_sources.yaml"
# Entries older than this (in days) are flagged for re-verification by the test suite and docs.
REVERIFY_AFTER_DAYS = 180


class UnknownSourceError(KeyError):
    pass


@lru_cache
def load_sources(path: Path = SOURCES_PATH) -> dict[str, RegulatorySource]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = [RegulatorySource.model_validate(item) for item in raw["sources"]]
    by_id = {s.id: s for s in sources}
    if len(by_id) != len(sources):
        raise ValueError("Duplicate source ids in the SEBI rulebook registry")
    return by_id


def get_source(source_id: str) -> RegulatorySource:
    try:
        return load_sources()[source_id]
    except KeyError:
        raise UnknownSourceError(f"'{source_id}' is not in the curated SEBI registry") from None


def get_sources(ids: list[str]) -> list[RegulatorySource]:
    return [get_source(i) for i in dict.fromkeys(ids)]


def stale_sources(today: date | None = None) -> list[RegulatorySource]:
    """Sources not re-verified within REVERIFY_AFTER_DAYS (or never verified)."""
    today = today or date.today()
    return [
        s
        for s in load_sources().values()
        if s.verified_on is None or (today - s.verified_on).days > REVERIFY_AFTER_DAYS
    ]
