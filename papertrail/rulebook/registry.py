"""SEBI register lookup: is a creator a registered investment adviser or research analyst?

Data comes from SEBI's public "Recognised Intermediaries" pages. Only the **name, registration
number, category and validity** are kept. Contact details on those pages (emails, phone numbers,
addresses) are personal data and are never stored.

How the local copy is built is deliberately conservative (see ADR-009): pages saved from SEBI's
public website are imported with ``import``. Automated refreshing waits until SEBI's website terms
have been reviewed and the project owner approves it.

Matching rules (ADR-009):
* A **registration number** match (INA… / INH…) is strong evidence.
* A **name** match is weaker: names can be shared or written differently. The result says which
  basis was used, and the UI asks the user to confirm on SEBI's site.
* "Not found" only means "not found in our copy". It is never shown as "unregistered".

CLI:
    uv run python -m papertrail.rulebook.registry import saved_page.html --category research_analyst
    uv run python -m papertrail.rulebook.registry lookup "Some Name"
"""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field
from rapidfuzz import fuzz, process

from papertrail.config import get_settings
from papertrail.models import REGISTRATION_NOT_ENDORSEMENT, RegistrationStatus, SebiRegistration

SEBI_REGISTER_URL = "https://www.sebi.gov.in/intermediaries.html"
NAME_MATCH_THRESHOLD = 92
REG_NO = re.compile(r"\bIN[AH][A-Z0-9]{9}\b")


class Category(StrEnum):
    INVESTMENT_ADVISER = "investment_adviser"
    RESEARCH_ANALYST = "research_analyst"


class RegistryEntry(BaseModel):
    name: str
    registration_number: str
    category: Category
    valid_from: date | None = None
    valid_to: date | None = Field(default=None, description="None means 'Perpetual'.")

    def is_valid_on(self, day: date) -> bool:
        if self.valid_from and day < self.valid_from:
            return False
        return self.valid_to is None or day <= self.valid_to


class Snapshot(BaseModel):
    snapshot_date: date
    source: str = SEBI_REGISTER_URL
    entries: list[RegistryEntry] = Field(default_factory=list)


# ------------------------------------------------------------------------------------------
# Parsing SEBI's public listing HTML
# ------------------------------------------------------------------------------------------

_CARD_FIELD = re.compile(
    r'<div class="title"><span>(?P<title>[^<]+)</span></div>\s*'
    r'<div class="value[^"]*"><span>(?P<value>.*?)</span></div>',
    re.DOTALL,
)
_KEEP = {"Name", "Registration No.", "Validity"}  # everything else is dropped on purpose


def _parse_date(text: str) -> date | None:
    text = text.strip()
    if not text or text.lower() == "perpetual":
        return None
    for fmt in ("%b %d, %Y", "%d %b %Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_register_html(page: str, category: Category) -> list[RegistryEntry]:
    """Extract (name, registration number, validity) from a saved SEBI register page."""
    entries: list[RegistryEntry] = []
    current: dict[str, str] = {}

    def flush() -> None:
        if current.get("Name") and current.get("Registration No."):
            validity = current.get("Validity", "")
            start, _, end = validity.partition(" - ")
            entries.append(
                RegistryEntry(
                    name=current["Name"],
                    registration_number=current["Registration No."].strip().upper(),
                    category=category,
                    valid_from=_parse_date(start),
                    valid_to=_parse_date(end),
                )
            )

    for m in _CARD_FIELD.finditer(page):
        title = m["title"].strip()
        if title not in _KEEP:
            continue
        if title == "Name":
            flush()
            current = {}
        current[title] = " ".join(html.unescape(re.sub(r"<[^>]+>", "", m["value"])).split())
    flush()
    return entries


# ------------------------------------------------------------------------------------------
# Name normalisation and lookup
# ------------------------------------------------------------------------------------------

_SUFFIXES = re.compile(
    r"\b(private|pvt|limited|ltd|llp|inc|co|company|and|proprietor|proprietorship|of|"
    r"the|mr|mrs|ms|dr)\b\.?",
    re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    name = html.unescape(name).lower().replace("&", " and ")
    name = re.sub(r"[^\w\s]", " ", name)
    name = _SUFFIXES.sub(" ", name)
    return " ".join(name.split())


def _name_variants(entry: RegistryEntry) -> list[str]:
    """The full name plus any proprietor / trade name inside brackets or after 'Proprietor'."""
    variants = [entry.name]
    inner = re.findall(r"\(([^)]*)\)", entry.name)
    variants += [re.sub(r"(?i)proprietor\s*:?\s*", "", v) for v in inner]
    outside = re.sub(r"\([^)]*\)", "", entry.name)
    variants.append(outside)
    parts = re.split(r"(?i)\bproprietor\s*(?:of|:)?\s*", outside)
    variants += parts
    return [v for v in {normalize_name(v) for v in variants} if v]


class Registry:
    def __init__(self, snapshot: Snapshot) -> None:
        self.snapshot = snapshot
        self._by_number = {e.registration_number: e for e in snapshot.entries}
        self._names: list[tuple[str, RegistryEntry]] = [
            (variant, e) for e in snapshot.entries for variant in _name_variants(e)
        ]

    @classmethod
    def load(cls, path: str | Path | None = None) -> Registry | None:
        p = Path(path or get_settings().registry_snapshot_path)
        if not p.exists():
            return None
        return cls(Snapshot.model_validate_json(p.read_text(encoding="utf-8")))

    def find_by_number(self, number: str) -> RegistryEntry | None:
        return self._by_number.get(number.strip().upper().replace("/", ""))

    def find_by_name(self, name: str) -> list[RegistryEntry]:
        query = normalize_name(name)
        if len(query) < 3:
            return []
        hits = process.extract(
            query, [n for n, _ in self._names], scorer=fuzz.token_sort_ratio, limit=5
        )
        seen: dict[str, RegistryEntry] = {}
        for _, score, idx in hits:
            if score >= NAME_MATCH_THRESHOLD:
                entry = self._names[idx][1]
                seen.setdefault(entry.registration_number, entry)
        return list(seen.values())


def _status_for(entries: list[RegistryEntry]) -> RegistrationStatus:
    cats = {e.category for e in entries}
    if cats == {Category.INVESTMENT_ADVISER, Category.RESEARCH_ANALYST}:
        return RegistrationStatus.REGISTERED_IA_AND_RA
    if Category.RESEARCH_ANALYST in cats:
        return RegistrationStatus.REGISTERED_RA
    return RegistrationStatus.REGISTERED_IA


def lookup_registration(
    registry: Registry | None,
    *,
    name: str | None = None,
    text: str = "",
    today: date | None = None,
) -> SebiRegistration:
    """Look up a creator by any registration number mentioned in ``text``, then by ``name``."""
    today = today or date.today()
    if registry is None:
        return SebiRegistration(
            status=RegistrationStatus.NOT_CHECKED,
            source_url=SEBI_REGISTER_URL,
            note=(
                "Our copy of SEBI's register is not loaded, so registration was not checked. "
                + REGISTRATION_NOT_ENDORSEMENT
            ),
        )

    base = dict(
        registry_snapshot_date=registry.snapshot.snapshot_date, source_url=SEBI_REGISTER_URL
    )
    mentioned = [n for n in dict.fromkeys(REG_NO.findall(text.upper()))]
    by_number = [e for n in mentioned if (e := registry.find_by_number(n))]
    if by_number:
        matches, basis = by_number, "registration_number"
    elif name:
        matches, basis = registry.find_by_name(name), "name"
    else:
        matches, basis = [], None

    if not matches:
        if mentioned:
            note = (
                f"The registration number(s) mentioned ({', '.join(mentioned)}) were not found in "
                f"our copy of SEBI's register dated {registry.snapshot.snapshot_date:%d %b %Y}. "
            )
        elif name:
            note = (
                f"No registration matching '{name}' was found in our copy of SEBI's register "
                f"dated {registry.snapshot.snapshot_date:%d %b %Y}. "
            )
        else:
            return SebiRegistration(
                status=RegistrationStatus.NOT_CHECKED,
                note="No creator name or registration number was given, so registration was "
                "not checked. " + REGISTRATION_NOT_ENDORSEMENT,
                **base,
            )
        return SebiRegistration(
            status=RegistrationStatus.NOT_FOUND,
            note=note + "This is not proof that the person is unregistered: names can be written "
            "differently and our copy can be out of date. Please check on SEBI's website.",
            **base,
        )

    current = [e for e in matches if e.is_valid_on(today)]
    if not current:
        return SebiRegistration(
            status=RegistrationStatus.NOT_FOUND,
            matched_name=matches[0].name,
            registration_numbers=[e.registration_number for e in matches],
            match_basis=basis,
            note="A matching registration was found, but its validity period has ended. Please "
            "check its current status on SEBI's website.",
            **base,
        )
    caution = (
        " This is a match by name only: confirm the registration number with the creator."
        if basis == "name"
        else ""
    )
    return SebiRegistration(
        status=_status_for(current),
        matched_name=current[0].name,
        registration_numbers=[e.registration_number for e in current],
        match_basis=basis,
        note=REGISTRATION_NOT_ENDORSEMENT + caution,
        **base,
    )


# ------------------------------------------------------------------------------------------
# Snapshot building
# ------------------------------------------------------------------------------------------


def import_pages(
    pages: list[tuple[str, Category]], output: Path, *, snapshot_date: date | None = None
) -> Snapshot:
    """Merge saved register pages into a snapshot JSON (only safe fields are written)."""
    existing = (
        Snapshot.model_validate_json(output.read_text(encoding="utf-8"))
        if output.exists()
        else None
    )
    by_number = {e.registration_number: e for e in (existing.entries if existing else [])}
    for page, category in pages:
        for entry in parse_register_html(page, category):
            by_number[entry.registration_number] = entry
    snap = Snapshot(
        snapshot_date=snapshot_date or date.today(),
        entries=sorted(by_number.values(), key=lambda e: e.name.lower()),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(snap.model_dump_json(indent=1), encoding="utf-8")
    return snap


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SEBI register snapshot tools")
    sub = parser.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("import", help="Import saved SEBI register HTML pages")
    imp.add_argument("files", nargs="+")
    imp.add_argument("--category", choices=[c.value for c in Category], required=True)
    imp.add_argument("--output", default=get_settings().registry_snapshot_path)
    look = sub.add_parser("lookup", help="Look up a name or registration number")
    look.add_argument("query")
    look.add_argument("--snapshot", default=get_settings().registry_snapshot_path)
    args = parser.parse_args(argv)

    if args.cmd == "import":
        pages = [(Path(f).read_text(encoding="utf-8"), Category(args.category)) for f in args.files]
        snap = import_pages(pages, Path(args.output))
        print(f"Snapshot now has {len(snap.entries)} entries -> {args.output}")
        return 0
    registry = Registry.load(args.snapshot)
    result = lookup_registration(registry, name=args.query, text=args.query)
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
