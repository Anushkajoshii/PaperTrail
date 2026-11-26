"""Fetch a public web page and extract its readable text, safely.

Safety measures:
* **SSRF guard.** Only http/https on standard ports, no credentials in URLs, and every address
  the host resolves to must be public. This blocks ``localhost``, private networks and the cloud
  metadata endpoint (169.254.169.254), which matters when this runs inside AWS Lambda.
  Redirects are followed by hand (at most 3), and each hop is re-checked.
* **Limits.** A timeout, a byte cap while streaming, a character cap on the extracted text, and
  HTML/plain text only.
* **Politeness.** robots.txt is respected, with an identifying User-Agent.
* **Untrusted content.** Text is cleaned with :func:`sanitize_untrusted_text` (see ADR-006).

Residual risk, documented in ADR-006: DNS can change between our check and the connection
(DNS rebinding). In production the worker Lambda also runs without access to internal services.
"""

from __future__ import annotations

import ipaddress
import json
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura

from papertrail.tools.untrusted import sanitize_untrusted_text

USER_AGENT = "PaperTrailBot/0.1 (+https://github.com/Anushkajoshii/PaperTrail)"
ALLOWED_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
MAX_REDIRECTS = 3

Resolver = Callable[..., list]


class FetchError(RuntimeError):
    pass


class BlockedURLError(FetchError):
    """The URL is not allowed (scheme, port, private address, robots.txt)."""


@dataclass
class FetchedPage:
    url: str
    final_url: str
    title: str
    site_name: str | None
    published: date | None
    text: str
    removed_instruction_count: int = 0
    truncated: bool = False


def _is_public(ip: str) -> bool:
    addr = ipaddress.ip_address(ip.split("%")[0])
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


def validate_url(url: str, resolver: Resolver = socket.getaddrinfo) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise BlockedURLError(f"Only http(s) URLs are allowed, got '{parsed.scheme}'")
    if not parsed.hostname:
        raise BlockedURLError("URL has no host")
    if parsed.username or parsed.password:
        raise BlockedURLError("URLs with embedded credentials are not allowed")
    if parsed.port not in (None, 80, 443):
        raise BlockedURLError(f"Port {parsed.port} is not allowed")
    try:
        infos = resolver(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError) as exc:
        raise FetchError(f"Could not resolve host '{parsed.hostname}'") from exc
    addresses = {info[4][0] for info in infos}
    if not addresses or not all(_is_public(a) for a in addresses):
        raise BlockedURLError(f"Host '{parsed.hostname}' resolves to a non-public address")
    return url


class PageFetcher:
    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        resolver: Resolver = socket.getaddrinfo,
        max_bytes: int = 2_000_000,
        max_chars: int = 20_000,
        timeout: float = 15.0,
        respect_robots: bool = True,
    ) -> None:
        self._client = client or httpx.Client(timeout=timeout)
        self._resolver = resolver
        self._max_bytes = max_bytes
        self._max_chars = max_chars
        self._respect_robots = respect_robots
        self._robots: dict[str, RobotFileParser | None] = {}

    @classmethod
    def from_settings(cls, s) -> PageFetcher:
        return cls(
            max_bytes=s.fetch_max_bytes,
            max_chars=s.fetch_max_chars,
            timeout=s.fetch_timeout_seconds,
        )

    # -- HTTP --------------------------------------------------------------------------------

    def _get(self, url: str) -> tuple[str, str, bytes]:
        """GET with manual, re-validated redirects and a byte cap. Returns (url, type, body)."""
        for _ in range(MAX_REDIRECTS + 1):
            validate_url(url, self._resolver)
            with self._client.stream(
                "GET", url, headers={"User-Agent": USER_AGENT}, follow_redirects=False
            ) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        raise FetchError("Redirect without a location")
                    url = urljoin(url, location)
                    continue
                if resp.status_code >= 400:
                    raise FetchError(f"HTTP {resp.status_code} for {url}")
                ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                body = bytearray()
                for chunk in resp.iter_bytes():
                    body.extend(chunk)
                    if len(body) > self._max_bytes:
                        raise FetchError(f"Page is larger than {self._max_bytes} bytes")
                return url, ctype, bytes(body)
        raise FetchError(f"Too many redirects (more than {MAX_REDIRECTS})")

    def _allowed_by_robots(self, url: str) -> bool:
        if not self._respect_robots:
            return True
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            parser: RobotFileParser | None = RobotFileParser()
            try:
                _, _, body = self._get(origin + "/robots.txt")
                parser.parse(body.decode("utf-8", errors="replace").splitlines())
            except BlockedURLError:
                raise
            except FetchError:
                parser = None  # no robots.txt (or unreachable): allowed
            self._robots[origin] = parser
        parser = self._robots[origin]
        return parser is None or parser.can_fetch(USER_AGENT, url)

    # -- Public ------------------------------------------------------------------------------

    def fetch(self, url: str) -> FetchedPage:
        validate_url(url, self._resolver)
        if not self._allowed_by_robots(url):
            raise BlockedURLError(f"robots.txt does not allow fetching {url}")
        final_url, ctype, body = self._get(url)
        if not ctype.startswith(ALLOWED_TYPES):
            raise FetchError(f"Unsupported content type '{ctype or 'unknown'}'")
        raw = body.decode("utf-8", errors="replace")

        title, site, published = "", None, None
        if ctype == "text/plain":
            text = raw
        else:
            extracted = trafilatura.extract(
                raw,
                url=final_url,
                output_format="json",
                with_metadata=True,
                include_comments=False,
                include_tables=True,
                favor_precision=True,
            )
            if not extracted:
                raise FetchError("No readable text found on the page")
            data = json.loads(extracted)
            text = data.get("text") or ""
            title = data.get("title") or ""
            site = data.get("sitename") or None
            published = _parse_date(data.get("date"))

        clean, removed = sanitize_untrusted_text(text)
        truncated = len(clean) > self._max_chars
        return FetchedPage(
            url=url,
            final_url=final_url,
            title=sanitize_untrusted_text(title)[0][:300],
            site_name=site,
            published=published,
            text=clean[: self._max_chars],
            removed_instruction_count=removed,
            truncated=truncated,
        )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
