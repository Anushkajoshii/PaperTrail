"""Load and validate the golden sets in ``evals/golden/``.

Validation is strict, so a typo in a label or a dangling evidence id fails CI instead of
silently skewing the numbers.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from papertrail.models import (
    ClaimType,
    Language,
    RedFlagKind,
    RegistrationStatus,
    SourceType,
    VerdictLabel,
)

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "evals" / "golden"
Split = Literal["smoke", "full"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GoldClaim(_Strict):
    text: str
    quote: str
    claim_type: ClaimType
    tickers: list[str] = Field(default_factory=list)


class GoldEvidence(_Strict):
    id: str
    url: str
    title: str
    source_type: SourceType
    published_at: date | None = None
    snippet: str


class GoldRegistration(_Strict):
    status: RegistrationStatus
    matched_name: str | None = None
    registration_numbers: list[str] = Field(default_factory=list)
    match_basis: str | None = None


class VerdictItem(_Strict):
    id: str
    split: Split
    language: Language
    claim: GoldClaim
    evidence: list[GoldEvidence] = Field(default_factory=list)
    registration: GoldRegistration | None = None
    gold_label: VerdictLabel
    gold_stances: dict[str, Literal["supports", "contradicts", "context", "irrelevant"]] = Field(
        default_factory=dict
    )
    why: str

    @model_validator(mode="after")
    def _stances_refer_to_evidence(self) -> VerdictItem:
        ids = {e.id for e in self.evidence}
        unknown = set(self.gold_stances) - ids
        if unknown:
            raise ValueError(f"{self.id}: gold_stances for unknown evidence {sorted(unknown)}")
        if self.claim.claim_type is ClaimType.CREDENTIAL and self.registration is None:
            raise ValueError(f"{self.id}: credential items need a registration fixture")
        return self


class GoldExtractedClaim(_Strict):
    anchor: str
    claim_type: ClaimType


class ExtractionItem(_Strict):
    id: str
    split: Split
    language: Language
    text: str
    claims: list[GoldExtractedClaim]
    not_claims: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _anchors_in_text(self) -> ExtractionItem:
        lower = self.text.lower()
        for c in self.claims:
            if c.anchor.lower() not in lower:
                raise ValueError(f"{self.id}: anchor '{c.anchor}' not in transcript")
        return self


class RulebookItem(_Strict):
    id: str
    split: Split
    text: str
    expect: list[RedFlagKind]
    registered: bool = False
    note: str | None = None


def _load(name: str, key: str, model: type[BaseModel], directory: Path) -> list:
    raw = yaml.safe_load((directory / name).read_text(encoding="utf-8"))
    items = [model.model_validate(x) for x in raw[key]]
    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate ids in {name}")
    return items


def _filter(items: list, split: Split) -> list:
    return [i for i in items if split == "full" or i.split == "smoke"]


def load_verdicts(split: Split = "full", directory: Path = GOLDEN_DIR) -> list[VerdictItem]:
    return _filter(_load("verdicts.yaml", "items", VerdictItem, directory), split)


def load_extraction(split: Split = "full", directory: Path = GOLDEN_DIR) -> list[ExtractionItem]:
    return _filter(_load("extraction.yaml", "transcripts", ExtractionItem, directory), split)


def load_rulebook(split: Split = "full", directory: Path = GOLDEN_DIR) -> list[RulebookItem]:
    return _filter(_load("rulebook.yaml", "sentences", RulebookItem, directory), split)
