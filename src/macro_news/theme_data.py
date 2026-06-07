from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable

import httpx

from .sample_data import BriefData, ThemeItem


@dataclass(frozen=True)
class ThemeSource:
    name: str
    feed_url: str
    source_id: str


@dataclass(frozen=True)
class ThemeRule:
    label: str
    keywords: tuple[str, ...]
    book_impact: str


@dataclass(frozen=True)
class ThemeCandidate:
    title: str
    source: str
    link: str
    text: str
    published_at: datetime | None
    matched_rule: ThemeRule
    matched_keywords: tuple[str, ...]
    score: int


@dataclass(frozen=True)
class ThemeDataResult:
    data: BriefData
    selected_titles: list[str]
    candidate_count: int
    fallback_used: bool
    errors: dict[str, str]
    sources: list[str]


THEME_SOURCES = [
    ThemeSource("Liberty Street Economics", "https://libertystreeteconomics.newyorkfed.org/feed/", "theme_feed:liberty_street_economics"),
    ThemeSource("Bank Underground", "https://bankunderground.co.uk/feed/", "theme_feed:bank_underground"),
    ThemeSource("FRED Blog", "https://fredblog.stlouisfed.org/feed/", "theme_feed:fred_blog"),
]

THEME_RULES = [
    ThemeRule(
        label="credit conditions and financial plumbing",
        keywords=("credit", "borrower", "loan", "lending", "rationing", "interest rate cap", "bank", "funding"),
        book_impact="What this means for our book: tighter credit access is a warning for risk appetite and EM debt selection.",
    ),
    ThemeRule(
        label="term premium and duration pressure",
        keywords=("term premium", "treasury", "duration", "long-term yield", "fiscal", "deficit", "auction", "debt"),
        book_impact="What this means for our book: duration pressure can support USD/JPY but challenge the gold overweight.",
    ),
    ThemeRule(
        label="policy divergence and USD/JPY",
        keywords=("dollar", "yen", "japan", "boj", "fed", "fomc", "policy rate", "central bank", "exchange rate"),
        book_impact="What this means for our book: keep USD/JPY tied to rate differentials and policy signals.",
    ),
    ThemeRule(
        label="inflation, rates, and gold",
        keywords=("inflation", "pce", "cpi", "energy", "oil", "real rate", "gold", "price stability", "labor cost"),
        book_impact="What this means for our book: inflation and rate evidence can either protect or pressure the gold overweight.",
    ),
    ThemeRule(
        label="EM debt and dollar funding",
        keywords=("emerging market", "em ", "sovereign", "external funding", "reserve", "current account", "india", "china", "policy uncertainty"),
        book_impact="What this means for our book: EM debt exposure should stay selective when dollar funding or policy uncertainty rises.",
    ),
    ThemeRule(
        label="China demand and commodities",
        keywords=("china", "commodity", "property", "trade", "industrial", "manufacturing", "pmi", "oil"),
        book_impact="What this means for our book: China-demand signals matter for commodities, EM risk, and global cyclicals.",
    ),
]


def _strip_html(value: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, *names: str) -> str:
    wanted = set(names)
    for child in list(element):
        if _local_name(child.tag) in wanted and child.text:
            return child.text.strip()
    return ""


def _link_text(element: ET.Element) -> str:
    for child in list(element):
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href:
            return href.strip()
        if child.text:
            return child.text.strip()
    return ""


def _published_at(element: ET.Element) -> datetime | None:
    raw_value = _child_text(element, "pubDate", "published", "updated", "date")
    if not raw_value:
        return None
    try:
        parsed = parsedate_to_datetime(raw_value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:'\w+)?\b", text))


def _trim_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(" ,;:") + "."


def _excerpt(text: str, max_words: int = 52) -> str:
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
    chosen: list[str] = []
    for sentence in sentences:
        next_text = " ".join([*chosen, sentence])
        if _word_count(next_text) > max_words:
            break
        chosen.append(sentence)
        if _word_count(next_text) >= 30:
            break
    if chosen:
        return " ".join(chosen)
    return _trim_words(text, max_words)


def _score_text(title: str, text: str, rule: ThemeRule) -> tuple[int, tuple[str, ...]]:
    title_lower = title.lower()
    text_lower = f"{title} {text}".lower()
    score = 0
    matches: list[str] = []
    for keyword in rule.keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in title_lower:
            score += 4
            matches.append(keyword)
        elif keyword_lower in text_lower:
            score += 1
            matches.append(keyword)
    return score, tuple(dict.fromkeys(matches))


def _best_rule(title: str, text: str) -> tuple[ThemeRule, tuple[str, ...], int]:
    best_rule = THEME_RULES[0]
    best_matches: tuple[str, ...] = ()
    best_score = 0
    for rule in THEME_RULES:
        score, matches = _score_text(title, text, rule)
        if score > best_score:
            best_rule = rule
            best_matches = matches
            best_score = score
    return best_rule, best_matches, best_score


def _summary_from_candidate(candidate: ThemeCandidate) -> str:
    excerpt = _excerpt(candidate.text)
    keywords = ", ".join(candidate.matched_keywords[:3]) or candidate.matched_rule.label
    summary = (
        f"Thesis: {candidate.title} is relevant to {candidate.matched_rule.label}. "
        f"Evidence: {excerpt} "
        f"The selector picked it because the feed discusses {keywords}. "
        "Portfolio link: it is a live source for judging whether the assumed FX, gold, or EM debt exposures need attention today."
    )
    if _word_count(summary) < 60:
        summary += " It should be read as a source input for portfolio-aware judgment, not as a standalone trade recommendation."
    return _trim_words(summary, 100)


def _parse_feed_item(item: ET.Element, source: ThemeSource) -> ThemeCandidate | None:
    title = _strip_html(_child_text(item, "title"))
    link = _link_text(item)
    description = _child_text(item, "description", "summary")
    if _word_count(_strip_html(description)) < 30:
        description = _child_text(item, "content", "encoded")
    text = _strip_html(description)
    if not title or not link or not text:
        return None

    matched_rule, matched_keywords, score = _best_rule(title, text)
    if score <= 0:
        return None
    return ThemeCandidate(
        title=title,
        source=source.name,
        link=link,
        text=text,
        published_at=_published_at(item),
        matched_rule=matched_rule,
        matched_keywords=matched_keywords,
        score=score,
    )


def parse_feed(xml_text: str, source: ThemeSource, max_items: int = 10) -> list[ThemeCandidate]:
    root = ET.fromstring(xml_text)
    items = [element for element in root.iter() if _local_name(element.tag) in {"item", "entry"}]
    candidates: list[ThemeCandidate] = []
    for item in items[:max_items]:
        candidate = _parse_feed_item(item, source)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def fetch_theme_candidates(
    client: httpx.Client,
    sources: list[ThemeSource] = THEME_SOURCES,
    max_items_per_source: int = 10,
) -> tuple[list[ThemeCandidate], dict[str, str], list[str]]:
    candidates: list[ThemeCandidate] = []
    errors: dict[str, str] = {}
    successful_sources: list[str] = []
    for source in sources:
        try:
            response = client.get(source.feed_url)
            response.raise_for_status()
            source_candidates = parse_feed(response.text, source, max_items=max_items_per_source)
        except Exception as exc:  # noqa: BLE001 - source-level fallback is intentional here.
            errors[source.source_id] = str(exc)
            continue
        if source_candidates:
            candidates.extend(source_candidates)
            successful_sources.append(source.source_id)
    return candidates, errors, successful_sources


def select_theme_candidates(candidates: list[ThemeCandidate], max_items: int = 2) -> list[ThemeCandidate]:
    ranked = sorted(
        candidates,
        key=lambda item: (
            -item.score,
            -(item.published_at.timestamp() if item.published_at else 0),
            item.title,
        ),
    )
    selected: list[ThemeCandidate] = []
    seen_sources: set[str] = set()
    seen_links: set[str] = set()
    seen_rules: set[str] = set()
    for candidate in ranked:
        if candidate.link in seen_links or candidate.source in seen_sources or candidate.matched_rule.label in seen_rules:
            continue
        selected.append(candidate)
        seen_sources.add(candidate.source)
        seen_links.add(candidate.link)
        seen_rules.add(candidate.matched_rule.label)
        if len(selected) >= max_items:
            return selected
    for candidate in ranked:
        if candidate.link in seen_links:
            continue
        selected.append(candidate)
        seen_links.add(candidate.link)
        if len(selected) >= max_items:
            return selected
    return selected


def candidate_to_theme_item(candidate: ThemeCandidate) -> ThemeItem:
    return ThemeItem(
        title=candidate.title,
        source=candidate.source,
        link=candidate.link,
        summary=_summary_from_candidate(candidate),
        book_impact=candidate.matched_rule.book_impact,
    )


def replace_theme_radar_with_live(
    data: BriefData,
    *,
    client_factory: Callable[[], httpx.Client] | None = None,
    sources: list[ThemeSource] = THEME_SOURCES,
) -> ThemeDataResult:
    client_factory = client_factory or (
        lambda: httpx.Client(
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; macro-news-agent/0.1)",
                "Accept-Encoding": "gzip, deflate",
            },
            follow_redirects=True,
        )
    )

    with client_factory() as client:
        candidates, errors, successful_sources = fetch_theme_candidates(client, sources=sources)
    selected = select_theme_candidates(candidates)
    if not selected:
        fallback_note = "Theme Radar: live RSS sources returned no usable candidates; scaffold source items used."
        fallback_data = replace(
            data,
            source_notes=[*[note for note in data.source_notes if not note.startswith("Theme Radar:")], fallback_note],
        )
        return ThemeDataResult(
            data=fallback_data,
            selected_titles=[],
            candidate_count=len(candidates),
            fallback_used=True,
            errors=errors or {"theme_sources": "no relevant source candidates found"},
            sources=successful_sources,
        )

    selected_sources = list(dict.fromkeys([*successful_sources, *[f"theme_selected:{candidate.source}" for candidate in selected]]))
    error_note = " One configured feed failed and is logged." if errors else ""
    theme_note = f"Theme Radar: selected {len(selected)} items from curated live RSS sources.{error_note}"
    updated = replace(
        data,
        theme_radar=[candidate_to_theme_item(candidate) for candidate in selected],
        assumptions=[
            *data.assumptions,
            "Theme Radar uses curated live RSS sources when available and sample fallback items when source collection fails.",
        ],
        data_sources=[*data.data_sources, *selected_sources],
        source_notes=[*[note for note in data.source_notes if not note.startswith("Theme Radar:")], theme_note],
    )
    return ThemeDataResult(
        data=updated,
        selected_titles=[candidate.title for candidate in selected],
        candidate_count=len(candidates),
        fallback_used=False,
        errors=errors,
        sources=selected_sources,
    )
