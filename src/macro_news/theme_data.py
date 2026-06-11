from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import quote_plus

import httpx

from .sample_data import BriefData, ThemeItem


@dataclass(frozen=True)
class ThemeSource:
    name: str
    feed_url: str
    source_id: str


@dataclass(frozen=True)
class ThemeSearchQuery:
    label: str
    query: str
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
    source_depth: str
    source_id: str


@dataclass(frozen=True)
class ArticleMetadata:
    title: str = ""
    description: str = ""
    site_name: str = ""
    published_at: datetime | None = None


@dataclass(frozen=True)
class ThemeDataResult:
    data: BriefData
    selected_titles: list[str]
    candidate_count: int
    fallback_used: bool
    errors: dict[str, str]
    sources: list[str]
    recent_repeat_titles: list[str] | None = None
    recent_topic_repeat_titles: list[str] | None = None


THEME_SOURCES = [
    ThemeSource("Liberty Street Economics", "https://libertystreeteconomics.newyorkfed.org/feed/", "theme_feed:liberty_street_economics"),
    ThemeSource("Bank Underground", "https://bankunderground.co.uk/feed/", "theme_feed:bank_underground"),
    ThemeSource("FRED Blog", "https://fredblog.stlouisfed.org/feed/", "theme_feed:fred_blog"),
]
DEFAULT_THEME_SEARCH_QUERIES = [
    ThemeSearchQuery("USD/JPY intervention", "USD JPY intervention yen Japan finance ministry", "theme_search:usd_jpy_intervention"),
    ThemeSearchQuery("Gold and yields", "gold Treasury yields real rates dollar", "theme_search:gold_yields"),
    ThemeSearchQuery("EM debt funding", "emerging market debt dollar funding Treasury yields", "theme_search:em_debt_funding"),
    ThemeSearchQuery("China demand", "China demand commodities property PMI oil", "theme_search:china_demand"),
]
DEFAULT_THEME_HISTORY_PATH = Path(".cache") / "theme_radar" / "history.json"
DEFAULT_THEME_RECENT_DAYS = 7
DEFAULT_THEME_METADATA_FETCH_LIMIT = 8
DEFAULT_THEME_ARTICLE_FETCH_LIMIT = 8
MIN_ARTICLE_TEXT_WORDS = 120
MAX_ARTICLE_TEXT_WORDS = 450
THEME_TOPIC_SIMILARITY_THRESHOLD = 0.6
RECENT_LINK_PENALTY = 6.0
RECENT_TOPIC_PENALTY = 7.0
SAME_RUN_TOPIC_PENALTY = 2.4
SAME_SOURCE_PENALTY = 0.8
SAME_RULE_PENALTY = 0.9
THEME_TOPIC_STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "always",
    "among",
    "because",
    "before",
    "being",
    "between",
    "could",
    "does",
    "from",
    "have",
    "into",
    "more",
    "over",
    "that",
    "their",
    "this",
    "through",
    "under",
    "when",
    "where",
    "which",
    "while",
    "with",
}
TRUSTED_NEWS_SOURCE_NAMES = (
    "Associated Press",
    "AP News",
    "Bank for International Settlements",
    "BBC",
    "Bloomberg",
    "Bloomberg.com",
    "CNBC",
    "Caixin Global",
    "ECB",
    "European Central Bank",
    "Federal Reserve",
    "Financial Times",
    "IMF",
    "International Monetary Fund",
    "Japan Times",
    "Nikkei Asia",
    "Reuters",
    "South China Morning Post",
    "The Economist",
    "The Wall Street Journal",
    "U.S. Bureau of Economic Analysis",
    "U.S. Bureau of Labor Statistics",
    "Wall Street Journal",
    "World Bank",
    "Yahoo Finance",
)
LIBERTY_STREET_HOME = "https://libertystreeteconomics.newyorkfed.org/"
BANK_UNDERGROUND_HOME = "https://bankunderground.co.uk/"

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


def _parse_datetime(value: str) -> datetime | None:
    raw_value = value.strip()
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


class _ArticleMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self._inside_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._inside_title = True
            return
        if tag.lower() != "meta":
            return
        attrs_dict = {key.lower(): (value or "").strip() for key, value in attrs}
        key = (attrs_dict.get("property") or attrs_dict.get("name") or "").lower()
        content = attrs_dict.get("content", "")
        if key and content:
            self.meta[key] = html.unescape(content)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title and data.strip():
            self._title_parts.append(data.strip())

    @property
    def title(self) -> str:
        return _strip_html(" ".join(self._title_parts))


class _ArticleTextParser(HTMLParser):
    _ignored_tags = {"script", "style", "nav", "header", "footer", "aside", "form", "button", "svg", "noscript"}
    _content_tags = {"p", "li"}
    _boilerplate_markers = {
        "accept cookies",
        "all rights reserved",
        "all posts",
        "cookie policy",
        "filed under",
        "look for our next post",
        "main |",
        "next post",
        "posted by",
        "previous post",
        "privacy policy",
        "related posts",
        "sign up",
        "subscribe",
    }

    def __init__(self) -> None:
        super().__init__()
        self.paragraphs: list[str] = []
        self._ignore_depth = 0
        self._active_tag: str | None = None
        self._active_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized in self._ignored_tags:
            self._ignore_depth += 1
            return
        if self._ignore_depth > 0:
            return
        if normalized in self._content_tags and self._active_tag is None:
            self._active_tag = normalized
            self._active_parts = []

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in self._ignored_tags and self._ignore_depth > 0:
            self._ignore_depth -= 1
            return
        if self._ignore_depth > 0:
            return
        if normalized == self._active_tag:
            text = _strip_html(" ".join(self._active_parts))
            if self._is_useful_paragraph(text):
                self.paragraphs.append(text)
            self._active_tag = None
            self._active_parts = []

    def handle_data(self, data: str) -> None:
        if self._ignore_depth == 0 and self._active_tag is not None and data.strip():
            self._active_parts.append(data.strip())

    def _is_useful_paragraph(self, text: str) -> bool:
        words = _word_count(text)
        if words < 12:
            return False
        lowered = text.lower()
        if any(marker in lowered for marker in self._boilerplate_markers):
            return False
        if "«" in text or "»" in text or text.count("|") >= 2:
            return False
        return True


def _extract_article_metadata(html_text: str) -> ArticleMetadata:
    parser = _ArticleMetadataParser()
    try:
        parser.feed(html_text)
    except Exception:  # noqa: BLE001 - malformed publisher HTML should not break a run.
        return ArticleMetadata()

    title = parser.meta.get("og:title") or parser.meta.get("twitter:title") or parser.title
    description = (
        parser.meta.get("og:description")
        or parser.meta.get("twitter:description")
        or parser.meta.get("description")
    )
    site_name = parser.meta.get("og:site_name") or parser.meta.get("application-name") or ""
    published_raw = (
        parser.meta.get("article:published_time")
        or parser.meta.get("article:modified_time")
        or parser.meta.get("date")
        or parser.meta.get("dc.date")
    )
    return ArticleMetadata(
        title=_strip_html(title or ""),
        description=_strip_html(description or ""),
        site_name=_strip_html(site_name),
        published_at=_parse_datetime(published_raw or ""),
    )


def _extract_article_text(
    html_text: str,
    *,
    min_words: int = MIN_ARTICLE_TEXT_WORDS,
    max_words: int = MAX_ARTICLE_TEXT_WORDS,
) -> str:
    parser = _ArticleTextParser()
    try:
        parser.feed(html_text)
    except Exception:  # noqa: BLE001 - malformed publisher HTML should not break a run.
        return ""
    text = _strip_leading_byline(_strip_html(" ".join(parser.paragraphs)))
    if _word_count(text) < min_words:
        return ""
    return _trim_words(text, max_words)


def _strip_leading_byline(text: str) -> str:
    opener = r"(?:In|The|A|An|Many|Several|Some|Over|During|Since|For|When|While|If)\b"
    byline_name = r"[A-Z][A-Za-z.\-']+(?:\s+[A-Z][A-Za-z.\-']+)*"
    byline_pattern = rf"^(?:{byline_name},\s+){{2,}}(?:and\s+)?{byline_name}\s+(?={opener})"
    return re.sub(byline_pattern, "", text).strip()


def _client_get(client: httpx.Client, url: str, *, timeout: float | None = None) -> httpx.Response:
    if timeout is None:
        return client.get(url)
    try:
        return client.get(url, timeout=timeout)
    except TypeError:
        return client.get(url)


def _can_enrich_with_article_metadata(candidate: ThemeCandidate) -> bool:
    if candidate.source_id.startswith("theme_search:"):
        return False
    return "news.google.com" not in candidate.link.lower()


def _source_depth_with(source_depth: str, addition: str) -> str:
    if addition.lower() in source_depth.lower():
        return source_depth
    return f"{source_depth} + {addition}"


def _metadata_text(metadata: ArticleMetadata) -> str:
    return _strip_html(" ".join(part for part in (metadata.title, metadata.description) if part))


def _enrich_candidate_with_article_context(client: httpx.Client, candidate: ThemeCandidate) -> ThemeCandidate:
    if not _can_enrich_with_article_metadata(candidate):
        return candidate
    try:
        response = _client_get(client, candidate.link, timeout=5)
        response.raise_for_status()
    except Exception:  # noqa: BLE001 - metadata enrichment is best-effort.
        return candidate

    metadata = _extract_article_metadata(response.text)
    article_text = _extract_article_text(response.text)
    if article_text:
        combined_text = f"{article_text} {candidate.text}".strip()
        matched_rule, matched_keywords, score = _best_rule(candidate.title, combined_text)
        return replace(
            candidate,
            text=combined_text,
            published_at=metadata.published_at or candidate.published_at,
            matched_rule=matched_rule,
            matched_keywords=matched_keywords,
            score=max(candidate.score, score),
            source_depth=_source_depth_with(candidate.source_depth, "article text excerpt"),
        )

    metadata_text = _metadata_text(metadata)
    if _word_count(metadata_text) < 18:
        if metadata.published_at and candidate.published_at is None:
            return replace(candidate, published_at=metadata.published_at)
        return candidate

    if metadata.description and metadata.description.lower() in candidate.text.lower():
        combined_text = candidate.text
    else:
        combined_text = f"{candidate.text} {metadata_text}".strip()
    matched_rule, matched_keywords, score = _best_rule(candidate.title, combined_text)
    return replace(
        candidate,
        text=combined_text,
        published_at=metadata.published_at or candidate.published_at,
        matched_rule=matched_rule,
        matched_keywords=matched_keywords,
        score=max(candidate.score, score),
        source_depth=_source_depth_with(candidate.source_depth, "article metadata"),
    )


def google_news_search_sources(queries: list[ThemeSearchQuery] | tuple[ThemeSearchQuery, ...]) -> list[ThemeSource]:
    sources: list[ThemeSource] = []
    for query in queries:
        encoded = quote_plus(query.query)
        sources.append(
            ThemeSource(
                f"Google News: {query.label}",
                f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en",
                query.source_id,
            )
        )
    return sources


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
    summary = (
        f"Thesis: {candidate.title} is relevant to {candidate.matched_rule.label}. "
        f"Evidence from the available {candidate.source_depth.lower()}: {excerpt} "
        "Portfolio link: use it as source input for judging whether the assumed FX, gold, or EM debt exposures need attention today."
    )
    if _word_count(summary) < 45:
        summary += " It should be read as a source input for portfolio-aware judgment, not as a standalone trade recommendation."
    return _trim_words(summary, 100)


def _is_search_source(source: ThemeSource) -> bool:
    return source.source_id.startswith("theme_search:")


def _is_trusted_search_source(source_name: str) -> bool:
    normalized = source_name.strip().lower()
    return any(normalized == trusted.lower() for trusted in TRUSTED_NEWS_SOURCE_NAMES)


def _feed_text_and_depth(item: ET.Element, source: ThemeSource) -> tuple[str, str]:
    description_text = _strip_html(_child_text(item, "description", "summary"))
    content_text = _strip_html(_child_text(item, "content", "encoded"))
    if _is_search_source(source):
        return description_text or content_text, "search result snippet"
    description_words = _word_count(description_text)
    content_words = _word_count(content_text)
    if content_words >= 30 and content_words >= description_words + 10:
        return content_text, "RSS content field"
    if description_text:
        return description_text, "RSS excerpt"
    if content_text:
        return content_text, "RSS content field"
    return "", "RSS excerpt"


def _parse_feed_item(item: ET.Element, source: ThemeSource) -> ThemeCandidate | None:
    title = _strip_html(_child_text(item, "title"))
    link = _link_text(item)
    text, source_depth = _feed_text_and_depth(item, source)
    if not title or not link or not text:
        return None

    display_source = source.name
    original_source = _strip_html(_child_text(item, "source"))
    if _is_search_source(source):
        if not original_source or not _is_trusted_search_source(original_source):
            return None
        display_source = f"{original_source} via Google News"

    matched_rule, matched_keywords, score = _best_rule(title, text)
    if score <= 0:
        return None
    return ThemeCandidate(
        title=title,
        source=display_source,
        link=link,
        text=text,
        published_at=_published_at(item),
        matched_rule=matched_rule,
        matched_keywords=matched_keywords,
        score=score,
        source_depth=source_depth,
        source_id=source.source_id,
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
    metadata_fetch_limit: int | None = None,
    article_fetch_limit: int | None = None,
) -> tuple[list[ThemeCandidate], dict[str, str], list[str]]:
    enrichment_limit = (
        article_fetch_limit
        if article_fetch_limit is not None
        else metadata_fetch_limit
        if metadata_fetch_limit is not None
        else DEFAULT_THEME_ARTICLE_FETCH_LIMIT
    )
    candidates: list[ThemeCandidate] = []
    errors: dict[str, str] = {}
    successful_sources: list[str] = []
    for source in sources:
        try:
            response = _client_get(client, source.feed_url)
            response.raise_for_status()
            source_candidates = parse_feed(response.text, source, max_items=max_items_per_source)
        except Exception as exc:  # noqa: BLE001 - source-level outage is logged per feed.
            errors[source.source_id] = str(exc)
            continue
        if source_candidates:
            candidates.extend(source_candidates)
            successful_sources.append(source.source_id)
    if enrichment_limit > 0:
        enrich_indexes = [
            index
            for index, candidate in sorted(
                enumerate(candidates),
                key=lambda item: (
                    -item[1].score,
                    -(item[1].published_at.timestamp() if item[1].published_at else 0),
                    item[1].title,
                ),
            )
            if _can_enrich_with_article_metadata(candidate)
        ][:enrichment_limit]
        for index in enrich_indexes:
            candidates[index] = _enrich_candidate_with_article_context(client, candidates[index])
    return candidates, errors, successful_sources


def _read_theme_history(history_path: Path) -> list[dict[str, str]]:
    if not history_path.exists():
        return []
    try:
        raw = json.loads(history_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _write_theme_history(history_path: Path, history: list[dict[str, str]]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history[-250:], indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _recent_links_before_today(history: list[dict[str, str]], run_date: date, recent_days: int) -> set[str]:
    recent_links: set[str] = set()
    for entry in history:
        link = str(entry.get("link", "")).strip()
        selected_date_raw = str(entry.get("selected_date", "")).strip()
        if not link or not selected_date_raw:
            continue
        try:
            selected_date = date.fromisoformat(selected_date_raw)
        except ValueError:
            continue
        if selected_date >= run_date:
            continue
        if (run_date - selected_date).days <= recent_days:
            recent_links.add(link)
    return recent_links


def _theme_topic_tokens(title: str) -> frozenset[str]:
    tokens: set[str] = set()
    for raw_token in re.findall(r"[a-z0-9]+", title.lower()):
        if len(raw_token) < 4 or raw_token in THEME_TOPIC_STOPWORDS:
            continue
        token = raw_token.removesuffix("s")
        aliases = {
            "treasurie": "treasury",
            "yield": "yield",
            "yields": "yield",
            "inflationary": "inflation",
            "japanese": "japan",
            "official": "official",
            "officials": "official",
            "warning": "warn",
            "warns": "warn",
            "rates": "rate",
        }
        tokens.add(aliases.get(token, token))
    return frozenset(tokens)


def _theme_topic_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def _is_near_duplicate_token_set(candidate_tokens: frozenset[str], prior_topic_tokens: list[frozenset[str]]) -> bool:
    return any(
        len(candidate_tokens & prior_tokens) >= 3
        and _theme_topic_similarity(candidate_tokens, prior_tokens) >= THEME_TOPIC_SIMILARITY_THRESHOLD
        for prior_tokens in prior_topic_tokens
    )


def _is_near_duplicate_topic(candidate: ThemeCandidate, recent_topic_tokens: list[frozenset[str]]) -> bool:
    candidate_tokens = _theme_topic_tokens(candidate.title)
    return _is_near_duplicate_token_set(candidate_tokens, recent_topic_tokens)


def _recent_topic_tokens_before_today(history: list[dict[str, str]], run_date: date, recent_days: int) -> list[frozenset[str]]:
    recent_topic_tokens: list[frozenset[str]] = []
    for entry in history:
        selected_date_raw = str(entry.get("selected_date", "")).strip()
        title = str(entry.get("title", "")).strip()
        if not title or not selected_date_raw:
            continue
        try:
            selected_date = date.fromisoformat(selected_date_raw)
        except ValueError:
            continue
        if selected_date >= run_date:
            continue
        if (run_date - selected_date).days <= recent_days:
            tokens = _theme_topic_tokens(title)
            if tokens:
                recent_topic_tokens.append(tokens)
    return recent_topic_tokens


def _append_theme_history(history_path: Path, run_date: date, selected: list[ThemeCandidate]) -> None:
    history = _read_theme_history(history_path)
    history.extend(
        {
            "selected_date": run_date.isoformat(),
            "title": candidate.title,
            "source": candidate.source,
            "link": candidate.link,
            "source_depth": candidate.source_depth,
            "topic_tokens": " ".join(sorted(_theme_topic_tokens(candidate.title))),
        }
        for candidate in selected
    )
    _write_theme_history(history_path, history)


def select_theme_candidates(
    candidates: list[ThemeCandidate],
    max_items: int = 2,
    *,
    recent_links: set[str] | None = None,
    recent_topic_tokens: list[frozenset[str]] | None = None,
) -> list[ThemeCandidate]:
    recent_links = recent_links or set()
    recent_topic_tokens = recent_topic_tokens or []
    selected: list[ThemeCandidate] = []
    seen_sources: set[str] = set()
    seen_links: set[str] = set()
    seen_rules: set[str] = set()
    selected_topic_tokens: list[frozenset[str]] = []
    remaining = list(candidates)

    def adjusted_rank(candidate: ThemeCandidate) -> tuple[float, int, float, str]:
        candidate_tokens = _theme_topic_tokens(candidate.title)
        adjusted_score = float(candidate.score)
        if candidate.link in recent_links:
            adjusted_score -= RECENT_LINK_PENALTY
        if _is_near_duplicate_topic(candidate, recent_topic_tokens):
            adjusted_score -= RECENT_TOPIC_PENALTY
        if _is_near_duplicate_token_set(candidate_tokens, selected_topic_tokens):
            adjusted_score -= SAME_RUN_TOPIC_PENALTY
        if candidate.source in seen_sources:
            adjusted_score -= SAME_SOURCE_PENALTY
        if candidate.matched_rule.label in seen_rules:
            adjusted_score -= SAME_RULE_PENALTY
        return (
            adjusted_score,
            candidate.score,
            candidate.published_at.timestamp() if candidate.published_at else 0.0,
            candidate.title,
        )

    while remaining and len(selected) < max_items:
        eligible = [candidate for candidate in remaining if candidate.link not in seen_links]
        if not eligible:
            break
        best = max(eligible, key=adjusted_rank)
        selected.append(best)
        seen_sources.add(best.source)
        seen_links.add(best.link)
        seen_rules.add(best.matched_rule.label)
        best_tokens = _theme_topic_tokens(best.title)
        if best_tokens:
            selected_topic_tokens.append(best_tokens)
        remaining = [candidate for candidate in remaining if candidate is not best]
    return selected


def candidate_to_theme_item(candidate: ThemeCandidate) -> ThemeItem:
    return ThemeItem(
        title=candidate.title,
        source=candidate.source,
        link=candidate.link,
        summary=_summary_from_candidate(candidate),
        book_impact=candidate.matched_rule.book_impact,
        source_depth=candidate.source_depth,
    )


def replace_theme_radar_with_live(
    data: BriefData,
    *,
    run_date: date | None = None,
    history_path: Path | None = None,
    recent_days: int = DEFAULT_THEME_RECENT_DAYS,
    client_factory: Callable[[], httpx.Client] | None = None,
    sources: list[ThemeSource] = THEME_SOURCES,
    search_queries: list[ThemeSearchQuery] | tuple[ThemeSearchQuery, ...] = (),
    metadata_fetch_limit: int | None = None,
    article_fetch_limit: int | None = None,
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

    all_sources = [*sources, *google_news_search_sources(search_queries)]
    with client_factory() as client:
        candidates, errors, successful_sources = fetch_theme_candidates(
            client,
            sources=all_sources,
            metadata_fetch_limit=metadata_fetch_limit,
            article_fetch_limit=article_fetch_limit,
        )
    history = _read_theme_history(history_path) if history_path and run_date else []
    recent_links = _recent_links_before_today(history, run_date, recent_days) if run_date else set()
    recent_topic_tokens = _recent_topic_tokens_before_today(history, run_date, recent_days) if run_date else []
    selected = select_theme_candidates(candidates, recent_links=recent_links, recent_topic_tokens=recent_topic_tokens)
    recent_repeat_titles = [candidate.title for candidate in selected if candidate.link in recent_links]
    recent_topic_repeat_titles = [
        candidate.title
        for candidate in selected
        if candidate.link not in recent_links and _is_near_duplicate_topic(candidate, recent_topic_tokens)
    ]
    if not selected:
        blank_note = (
            "Theme Radar: no verified live RSS/search candidates available from "
            f"[Liberty Street Economics]({LIBERTY_STREET_HOME}), "
            f"[Bank Underground]({BANK_UNDERGROUND_HOME}), or "
            "FRED Blog/search sources; section left blank rather than using scaffold source items."
        )
        blank_data = replace(
            data,
            theme_radar=[],
            source_notes=[*[note for note in data.source_notes if not note.startswith("Theme Radar:")], blank_note],
        )
        return ThemeDataResult(
            data=blank_data,
            selected_titles=[],
            candidate_count=len(candidates),
            fallback_used=True,
            errors=errors or {"theme_sources": "no relevant source candidates found"},
            sources=successful_sources,
            recent_repeat_titles=[],
            recent_topic_repeat_titles=[],
        )

    if history_path and run_date:
        _append_theme_history(history_path, run_date, selected)

    selected_source_names = list(dict.fromkeys(candidate.source for candidate in selected))
    selected_sources = list(dict.fromkeys([*successful_sources, *[f"theme_selected:{candidate.source}" for candidate in selected]]))
    failed_note = ""
    if errors:
        failed_note = f" {len(errors)} configured Theme Radar source(s) failed and are logged."
    repeat_note = ""
    if recent_repeat_titles:
        repeat_note = " Recent-link memory penalized a repeat, but the item still ranked highly enough to select."
    if recent_topic_repeat_titles:
        repeat_note += " Recent-topic memory penalized a similar topic, but current relevance kept it in the selection."
    theme_note = (
        "Theme Radar: selected "
        f"{len(selected)} items from live RSS/search sources: "
        f"{', '.join(selected_source_names)}."
        f"{failed_note}{repeat_note}"
    )
    updated = replace(
        data,
        theme_radar=[candidate_to_theme_item(candidate) for candidate in selected],
        assumptions=[
            *data.assumptions,
            (
                "Theme Radar live mode uses curated RSS source text, best-effort article text excerpts, "
                "and article metadata when available "
                f"([Liberty Street Economics]({LIBERTY_STREET_HOME}), "
                f"[Bank Underground]({BANK_UNDERGROUND_HOME}), "
                "FRED Blog, and no-key news RSS search) and leaves the section blank rather than using scaffold source items when no verified candidates exist."
            ),
            (
                "Theme Radar recent-link rule: links selected before the current run date receive a strong penalty for "
                f"{recent_days} days, not an absolute ban; same-day reruns may repeat entries."
            ),
            (
                "Theme Radar near-duplicate rule: recently selected headline topics receive a novelty penalty, not a hard restriction; "
                "important current items can still win, and same-day reruns may repeat topics."
            ),
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
        recent_repeat_titles=recent_repeat_titles,
        recent_topic_repeat_titles=recent_topic_repeat_titles,
    )
