"""Wikimedia-backed reference vehicle image lookup — India-market aware.

Resolves a make + model (+ optional year and body-style category) to a
representative photo in two compliant tiers, both via official Wikimedia
APIs (never scraped HTML, never hotlinked by the frontend):

1. English Wikipedia article selection. Candidate articles are
   discovered per make-alias with `generator=prefixsearch` (so
   generation-disambiguated titles like "Suzuki Baleno (2015)" are
   found, not just the bare nameplate article) and then *verified*
   against the claim's structured identity before their lead image is
   trusted:

     - identity coupling: a page only qualifies if its title is exactly
       "{make-alias} {model}" (an optional trailing "(...)"
       disambiguator is allowed) or it was reached from such a title by
       a whole-page redirect. A *section* redirect (`tofragment`) means
       the marketed name is merely a paragraph inside another model's
       article — its lead image shows that other model, so the page is
       rejected outright (e.g. "MG Astor" -> "MG ZS (crossover)#1st").
     - year: a "(YYYY)" generation disambiguator and production ranges
       parsed from the intro keep a 2018 claim off an article whose
       production ended years earlier.
     - body style: the claim's catalog category must not contradict the
       intro's body-style wording (hatchback vs sedan vs SUV).
     - market: intros mentioning India outrank ones that don't.
     - nameplate-index articles ("the X nameplate has been used for
       several different cars...") are penalized — their lead image is
       one arbitrary generation.

2. Wikimedia Commons exact-name category. India-market identities that
   have no Wikipedia article of their own usually do have a Commons
   category under their exact marketed name (e.g. "Category:MG Astor"
   holds real India-market Astor photos). Only exact category titles
   are tried — never full-text search — so a miss stays a miss instead
   of becoming a related-but-wrong vehicle.

If neither tier produces a confidently-correct image the caller keeps
its neutral category illustration: a missing image is better than a
confidently incorrect car.

The resolved image is downloaded server-side and returned as bytes:
callers persist it locally and serve it from this application's own
`/vehicle-images/` route. No API key is involved anywhere in this flow,
so there is nothing that could leak to the frontend. Every download is
validated to actually be an image (host allow-list, Content-Type, then
a Pillow decode) before it is accepted.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from typing import NamedTuple, Optional

import httpx
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
# Wikimedia's User-Agent policy requires an identifying agent WITH a
# contact address — requests without one are rejected with 403.
USER_AGENT = (
    f"ClaimSightIndia/0.1 (vehicle reference image resolver; "
    f"contact: bhavayvasudev@gmail.com) httpx/{httpx.__version__}"
)
THUMBNAIL_WIDTH = 800
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024
# Only ever download from Wikimedia's own media host — the API response
# is trusted for discovery, but the download URL is still pinned.
ALLOWED_IMAGE_HOSTS = {"upload.wikimedia.org"}

_TIMEOUT = httpx.Timeout(8.0, connect=4.0)

# Catalog manufacturer names -> the shorter forms Wikipedia article
# titles actually use ("Tata Nexon", not "Tata Motors Nexon"). The full
# catalog name is always tried first; these are additional candidates.
MAKE_TITLE_ALIASES: dict[str, list[str]] = {
    "maruti suzuki": ["Suzuki", "Maruti"],
    "tata motors": ["Tata"],
    "mg motor": ["MG"],
    "force motors": ["Force"],
    "hindustan motors": ["Hindustan"],
}

# Catalog categories -> body-style words an article intro would use.
# Only the three styles that get genuinely confused with each other
# participate in the *conflict* penalty; the rest only earn the match
# bonus (a "Luxury Car" is a price class, not a body style).
BODY_STYLE_KEYWORDS: dict[str, frozenset[str]] = {
    "hatchback": frozenset({"hatchback"}),
    "sedan": frozenset({"sedan", "saloon"}),
    "suv": frozenset({"suv", "crossover"}),
    "bus": frozenset({"bus"}),
    "truck": frozenset({"truck", "lorry", "pickup"}),
    "commercial vehicle": frozenset({"van", "minivan", "pickup", "truck"}),
}
_CONFLICTING_STYLES = ("hatchback", "sedan", "suv")

# A page must reach this score to have its lead image trusted. Identity
# alone (+3) qualifies; any structural contradiction (wrong era, wrong
# body style, multi-generation nameplate index) drags it below.
ACCEPT_SCORE_THRESHOLD = 3

_PIL_FORMAT_TO_EXTENSION = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


class RemoteVehicleImage(NamedTuple):
    content: bytes
    extension: str  # "jpg" | "png" | "webp"
    page_title: str


@dataclass
class PageCandidate:
    """One Wikipedia page that passed identity coupling and is eligible
    for scoring."""

    title: str
    extract: str
    thumbnail_url: Optional[str]


def candidate_titles(make: str, model: str) -> list[str]:
    """Wikipedia article titles worth trying for this make/model, in
    priority order. The model name is never used without a manufacturer
    prefix, and variant/trim is deliberately excluded — article titles
    cover the model line."""
    make = make.strip()
    model = model.strip()
    titles = [f"{make} {model}"]
    for alias in MAKE_TITLE_ALIASES.get(make.lower(), []):
        titles.append(f"{alias} {model}")
    # De-duplicate while preserving order.
    seen: set[str] = set()
    return [t for t in titles if not (t.lower() in seen or seen.add(t.lower()))]


_PARENTHETICAL_RE = re.compile(r"\s*\(([^)]*)\)\s*$")
_TITLE_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _base_title(title: str) -> str:
    """"Suzuki Baleno (2015)" -> "suzuki baleno" — the identity part of a
    possibly generation-disambiguated article title."""
    return _PARENTHETICAL_RE.sub("", title).strip().lower()


def _title_generation_year(title: str) -> Optional[int]:
    match = _PARENTHETICAL_RE.search(title)
    if not match:
        return None
    year_match = _TITLE_YEAR_RE.search(match.group(1))
    return int(year_match.group(0)) if year_match else None


_OPEN_RANGE_RE = re.compile(r"\bsince\s+(?:[a-z]+\s+)?((?:19|20)\d{2})\b", re.IGNORECASE)
_CLOSED_RANGE_RES = (
    re.compile(r"\bfrom\s+((?:19|20)\d{2})\s+(?:to|until)\s+((?:19|20)\d{2})\b", re.IGNORECASE),
    re.compile(r"\bbetween\s+((?:19|20)\d{2})\s+and\s+((?:19|20)\d{2})\b", re.IGNORECASE),
    re.compile(r"\b((?:19|20)\d{2})\s*[–—-]\s*((?:19|20)\d{2})\b"),
    re.compile(r"\buntil\s+((?:19|20)\d{2})\b", re.IGNORECASE),
)


def _production_year_signals(extract: str) -> tuple[list[int], list[int]]:
    """(open-range start years, closed-range end years) parsed from an
    article intro — e.g. "since 2015" -> ([2015], []), "from 1996 to
    2002 ... until 2007" -> ([], [2002, 2007])."""
    opens = [int(m.group(1)) for m in _OPEN_RANGE_RE.finditer(extract)]
    ends: list[int] = []
    for pattern in _CLOSED_RANGE_RES:
        for m in pattern.finditer(extract):
            ends.append(int(m.group(m.re.groups)))
    return opens, ends


_NAMEPLATE_INDEX_RE = re.compile(
    r"nameplate has been (?:used|applied)|several different", re.IGNORECASE
)


def _is_nameplate_index(extract: str) -> bool:
    """True for intros whose *subject* is a nameplate reused across
    several distinct vehicles ("The X nameplate has been used to denote
    several different cars...") — their lead image is one arbitrary
    generation. A current-model article merely *mentioning* its
    nameplate's earlier use (e.g. "the Swift nameplate was previously
    applied to...") must not match."""
    return bool(_NAMEPLATE_INDEX_RE.search(extract))


def score_page(
    page: PageCandidate,
    *,
    year: Optional[int] = None,
    vehicle_type: Optional[str] = None,
) -> int:
    """Relevance of a (already identity-coupled) page for the claim's
    structured vehicle identity. Additive so each signal stays
    independently testable."""
    score = 3  # identity coupling — the page is this make+model by title
    extract = page.extract or ""
    lowered = extract.lower()

    if _is_nameplate_index(extract):
        score -= 2

    if "india" in lowered:
        score += 1

    generation_year = _title_generation_year(page.title)
    if year is not None and generation_year is not None:
        score += 2 if generation_year <= year else -2

    if year is not None:
        opens, ends = _production_year_signals(extract)
        if opens and min(opens) <= year and not _is_nameplate_index(extract):
            score += 1
        if ends and not opens and max(ends) < year:
            score -= 3

    style_words = BODY_STYLE_KEYWORDS.get((vehicle_type or "").strip().lower())
    if style_words:
        if any(word in lowered for word in style_words):
            score += 2
        elif (vehicle_type or "").strip().lower() in _CONFLICTING_STYLES:
            other_words = {
                word
                for style in _CONFLICTING_STYLES
                if style != (vehicle_type or "").strip().lower()
                for word in BODY_STYLE_KEYWORDS[style]
            }
            if any(word in lowered for word in other_words):
                score -= 2

    return score


def parse_page_candidates(api_response: dict, accepted_titles: list[str]) -> list[PageCandidate]:
    """Pages from one prefixsearch-generator response that are actually
    this make+model, per the identity rules in the module docstring.
    Prefixsearch returns plenty of noise ("MG Astor" also surfaces
    "Masters of Horror") — everything not identity-coupled is dropped
    here, before scoring."""
    query = api_response.get("query") or {}
    accepted = {t.strip().lower() for t in accepted_titles}

    redirect_identity: set[str] = set()
    fragment_targets: set[str] = set()
    for redirect in query.get("redirects", []):
        source = (redirect.get("from") or "").strip().lower()
        target = redirect.get("to") or ""
        if source not in accepted:
            continue
        if redirect.get("tofragment"):
            # The marketed name is a *section* of another model's
            # article — that article's lead image is a different car.
            fragment_targets.add(target)
        else:
            redirect_identity.add(target)

    candidates: list[PageCandidate] = []
    for page in (query.get("pages") or {}).values():
        title = page.get("title") or ""
        if not title or "missing" in page:
            continue
        if title in fragment_targets:
            continue
        if "disambiguation" in (page.get("pageprops") or {}):
            continue
        if _base_title(title) not in accepted and title not in redirect_identity:
            continue
        candidates.append(
            PageCandidate(
                title=title,
                extract=page.get("extract") or "",
                thumbnail_url=(page.get("thumbnail") or {}).get("source"),
            )
        )
    return candidates


def select_best_page(
    pages: list[PageCandidate],
    *,
    year: Optional[int] = None,
    vehicle_type: Optional[str] = None,
) -> Optional[PageCandidate]:
    """Highest-scoring page with a usable image, or None when nothing
    clears ACCEPT_SCORE_THRESHOLD — never 'the least bad guess'."""
    best: Optional[PageCandidate] = None
    best_score = ACCEPT_SCORE_THRESHOLD - 1
    for page in pages:
        if not page.thumbnail_url:
            continue
        score = score_page(page, year=year, vehicle_type=vehicle_type)
        if score > best_score:
            best = page
            best_score = score
    return best


# Category members that are brand art rather than a photo of the car.
_NON_PHOTO_FILE_RE = re.compile(r"logo|badge|emblem|wordmark|brochure", re.IGNORECASE)


def prefer_commons_file(file_titles: list[str]) -> Optional[str]:
    """Deterministic pick from an exact-name Commons category: skip
    brand art, prefer files shot in India, then front views, then the
    first listed."""
    photos = [t for t in file_titles if not _NON_PHOTO_FILE_RE.search(t)]
    if not photos:
        return None
    for predicate in (
        lambda t: "india" in t.lower() and "front" in t.lower(),
        lambda t: "india" in t.lower(),
        lambda t: "front" in t.lower(),
    ):
        for title in photos:
            if predicate(title):
                return title
    return photos[0]


def _validated_image(content: bytes) -> Optional[str]:
    """Returns the file extension if the bytes decode as a supported
    image, else None. Never trust the URL or Content-Type alone."""
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
            return _PIL_FORMAT_TO_EXTENSION.get(img.format or "")
    except (UnidentifiedImageError, OSError, ValueError):
        return None


async def _download_validated(client: httpx.AsyncClient, url: str) -> Optional[tuple[bytes, str]]:
    """Downloads url (Wikimedia media host only) and returns (bytes,
    extension) after size / Content-Type / Pillow validation."""
    parsed = httpx.URL(url)
    if parsed.scheme != "https" or parsed.host not in ALLOWED_IMAGE_HOSTS:
        logger.warning("Rejected non-Wikimedia image host: %s", parsed.host)
        return None

    response = await client.get(url)
    response.raise_for_status()
    content = response.content

    if len(content) > MAX_DOWNLOAD_BYTES:
        logger.warning("Wikimedia image exceeds size cap; skipping: %s", url)
        return None
    if not response.headers.get("Content-Type", "").startswith("image/"):
        logger.warning("Wikimedia URL is not an image: %s", url)
        return None
    extension = _validated_image(content)
    if extension is None:
        logger.warning("Wikimedia download failed image validation: %s", url)
        return None
    return content, extension


async def _wikipedia_pages_for_candidate(
    client: httpx.AsyncClient, candidate: str, accepted_titles: list[str]
) -> list[PageCandidate]:
    response = await client.get(
        WIKIPEDIA_API_URL,
        params={
            "action": "query",
            "format": "json",
            "generator": "prefixsearch",
            "gpssearch": candidate,
            "gpslimit": 8,
            "redirects": 1,
            "prop": "pageprops|extracts|pageimages",
            "ppprop": "disambiguation",
            "exintro": 1,
            "explaintext": 1,
            "exsentences": 3,
            "exlimit": "max",
            "piprop": "thumbnail",
            "pithumbsize": THUMBNAIL_WIDTH,
        },
    )
    response.raise_for_status()
    return parse_page_candidates(response.json(), accepted_titles)


async def _resolve_from_commons(
    client: httpx.AsyncClient, candidates: list[str]
) -> Optional[RemoteVehicleImage]:
    """Exact marketed-name Commons category lookup — the rescue tier for
    India-market identities without their own Wikipedia article."""
    for candidate in candidates:
        category = f"Category:{candidate}"
        response = await client.get(
            COMMONS_API_URL,
            params={
                "action": "query",
                "format": "json",
                "list": "categorymembers",
                "cmtitle": category,
                "cmtype": "file",
                "cmlimit": 50,
            },
        )
        response.raise_for_status()
        members = (response.json().get("query") or {}).get("categorymembers") or []
        file_title = prefer_commons_file([m.get("title", "") for m in members if m.get("title")])
        if not file_title:
            continue

        info_response = await client.get(
            COMMONS_API_URL,
            params={
                "action": "query",
                "format": "json",
                "titles": file_title,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": THUMBNAIL_WIDTH,
            },
        )
        info_response.raise_for_status()
        pages = ((info_response.json().get("query") or {}).get("pages") or {}).values()
        thumb_url = next(
            (
                (info.get("thumburl") or info.get("url"))
                for page in pages
                for info in page.get("imageinfo") or []
            ),
            None,
        )
        if not thumb_url:
            continue

        downloaded = await _download_validated(client, thumb_url)
        if downloaded is None:
            continue
        content, extension = downloaded
        logger.info("Resolved '%s' from Commons category '%s'", candidate, category)
        return RemoteVehicleImage(content=content, extension=extension, page_title=candidate)
    return None


async def resolve_remote_vehicle_image(
    make: str,
    model: str,
    *,
    year: Optional[int] = None,
    vehicle_type: Optional[str] = None,
) -> Optional[RemoteVehicleImage]:
    """Bounded API round-trips + one validated download, or None. Never
    raises on network/HTTP/validation failure — callers treat None as
    'fall back to the category illustration and retry later'."""
    candidates = candidate_titles(make, model)
    if not candidates:
        return None

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
            pages: list[PageCandidate] = []
            seen_titles: set[str] = set()
            for candidate in candidates:
                for page in await _wikipedia_pages_for_candidate(client, candidate, candidates):
                    if page.title.lower() not in seen_titles:
                        seen_titles.add(page.title.lower())
                        pages.append(page)

            best = select_best_page(pages, year=year, vehicle_type=vehicle_type)
            if best is not None and best.thumbnail_url:
                downloaded = await _download_validated(client, best.thumbnail_url)
                if downloaded is not None:
                    content, extension = downloaded
                    return RemoteVehicleImage(
                        content=content, extension=extension, page_title=best.title
                    )

            # No confidently-correct Wikipedia article — try the exact
            # marketed-name Commons category before giving up.
            return await _resolve_from_commons(client, candidates)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Wikimedia image lookup failed for '%s %s': %s", make, model, exc)
        return None
