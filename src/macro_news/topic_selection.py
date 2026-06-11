from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from .portfolio import PositionEntry, active_positions, read_position_entries
from .sample_data import BriefData, CalendarEvent, MarketRow, ThemeItem


@dataclass(frozen=True)
class TopicCandidate:
    title: str
    origin: str
    portfolio_asset: str
    position: str
    exposure: str
    related_assets: tuple[str, ...]
    evidence: tuple[str, ...]
    required_terms: tuple[str, ...]
    group: str
    score: float
    source_label: str = ""
    link: str = ""
    score_components: tuple[tuple[str, float], ...] = ()


CHART_SOURCE_BY_ASSET = {
    "S&P 500": ("Yahoo Finance S&P 500 chart data", "https://finance.yahoo.com/quote/%5EGSPC/"),
    "Euro Stoxx 50": ("Yahoo Finance Euro Stoxx 50 chart data", "https://finance.yahoo.com/quote/%5ESTOXX50E/"),
    "US 10Y yield": ("Yahoo Finance US 10Y chart data", "https://finance.yahoo.com/quote/%5ETNX/"),
    "China internet / tech basket": ("Yahoo Finance KWEB chart data", "https://finance.yahoo.com/quote/KWEB/"),
    "DXY": ("Yahoo Finance DXY chart data", "https://finance.yahoo.com/quote/DX-Y.NYB/"),
    "EUR/USD": ("Frankfurter EUR/USD daily reference rates", "https://frankfurter.dev/"),
    "USD/JPY": ("Frankfurter USD/JPY daily reference rates", "https://frankfurter.dev/"),
    "Gold": ("Yahoo Finance gold futures chart data", "https://finance.yahoo.com/quote/GC=F/"),
    "Brent oil": ("Yahoo Finance Brent oil futures chart data", "https://finance.yahoo.com/quote/BZ=F/"),
    "WTI oil": ("Yahoo Finance WTI oil futures chart data", "https://finance.yahoo.com/quote/CL=F/"),
    "VIX": ("Yahoo Finance VIX chart data", "https://finance.yahoo.com/quote/%5EVIX/"),
}

DIRECT_PORTFOLIO_LINK_BONUS = 0.7
INDIRECT_RELEVANCE_MULTIPLIER = 0.65


def _clean_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _exposure_weight(exposure: str) -> float:
    return {
        "high": 3.0,
        "medium": 2.0,
        "low": 1.0,
    }.get(exposure.lower(), 1.5)


def _position_weight(position: str) -> float:
    lowered = position.lower()
    if lowered == "watch":
        return 0.8
    if lowered in {"long", "short", "overweight", "underweight", "short duration", "exposed"}:
        return 1.1
    return 1.0


def _change_score(change: str) -> float:
    normalized = change.strip().lower().replace(" ", "")
    if not normalized or normalized == "n/a":
        return 0.0
    try:
        if normalized.endswith("bp"):
            return min(abs(float(normalized.removesuffix("bp"))) / 5.0, 3.0)
        if normalized.endswith("%"):
            return min(abs(float(normalized.removesuffix("%"))), 3.0)
    except ValueError:
        return 0.0
    return 0.0


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _asset_matches(left: str, right: str) -> bool:
    return _clean_key(left) == _clean_key(right)


def _position_profile(entry: PositionEntry) -> tuple[str, tuple[str, ...], tuple[str, ...], str]:
    key = _clean_key(entry.asset)
    if "usd jpy" in key:
        return (
            "USD/JPY Intervention Risk",
            ("USD/JPY", "Japan 10Y yield", "US 10Y yield", "DXY"),
            ("usd/jpy", "yen", "intervention", "japan"),
            "fx",
        )
    if key == "gold":
        return (
            "Gold And Rates Pressure",
            ("Gold", "US 10Y yield", "DXY"),
            ("gold", "rate", "yield", "dollar"),
            "gold",
        )
    if "em debt" in key or "emerging market" in key:
        return (
            "EM Debt Conditions",
            ("US 10Y yield", "DXY", "S&P 500", "China internet / tech basket", "Brent oil", "WTI oil"),
            ("em debt", "em duration", "emerging market", "dollar", "rates"),
            "em",
        )
    if "us 10y" in key or "treasury" in key:
        return (
            "US Duration And Term Premium",
            ("US 10Y yield", "DXY", "Gold", "S&P 500"),
            ("us 10y", "treasury", "duration", "term premium", "rates"),
            "rates",
        )
    if "eur usd" in key:
        return (
            "EUR/USD And Dollar Mix",
            ("EUR/USD", "DXY", "US 10Y yield"),
            ("eur/usd", "euro", "dollar", "dxy"),
            "fx",
        )
    if "s p 500" in key or "sp 500" in key:
        return (
            "Equity Risk Tone",
            ("S&P 500", "Euro Stoxx 50", "VIX"),
            ("s&p", "equities", "equity", "risk"),
            "equity",
        )
    if "china internet" in key or "china tech" in key:
        return (
            "China Tech Sentiment",
            ("China internet / tech basket", "S&P 500", "DXY"),
            ("china", "tech", "internet", "kweb"),
            "china",
        )
    if "brent" in key or "oil" in key:
        return (
            "Oil And Inflation Risk",
            ("Brent oil", "WTI oil", "US 10Y yield", "Gold"),
            ("oil", "brent", "wti", "inflation"),
            "oil",
        )
    if key == "vix" or "volatility" in key:
        return (
            "Volatility Regime Watch",
            ("VIX", "S&P 500", "Euro Stoxx 50"),
            ("vix", "volatility", "hedging", "risk"),
            "volatility",
        )
    return (
        f"{entry.asset} Watch",
        (entry.asset,),
        tuple(term for term in _clean_key(entry.asset).split() if term),
        key,
    )


def _position_relevance(entry: PositionEntry, text: str, related_assets: tuple[str, ...] = ()) -> tuple[float, float]:
    _title, _profile_related_assets, required_terms, _group = _position_profile(entry)
    text_haystack = text.lower()
    keyword_sets = {
        "usd/jpy": ("usd/jpy", "jpy", "yen", "boj", "japan", "intervention"),
        "gold": ("gold", "inflation", "cpi", "ppi", "pce", "rates", "yield", "dollar", "real"),
        "em debt": ("em", "emerging", "china", "cny", "dollar", "usd", "rates", "yield", "risk", "pmi", "m2"),
        "us 10y": ("us 10y", "treasury", "fed", "fomc", "usd", "cpi", "ppi", "pce", "inflation", "rates", "yield"),
        "eur/usd": ("eur", "euro", "ecb", "eur/usd", "dollar", "rates"),
        "s&p 500": ("s&p", "spx", "equity", "equities", "risk", "growth", "vix"),
        "china internet": ("china", "cny", "pmi", "m2", "tech", "internet", "growth"),
        "brent": ("oil", "brent", "wti", "inflation", "geopolitical", "energy"),
        "vix": ("vix", "volatility", "risk", "hedging", "equity", "equities"),
    }
    entry_key = _clean_key(entry.asset)
    extra_terms: tuple[str, ...] = ()
    for key, terms in keyword_sets.items():
        if key.replace("/", " ") in entry_key or key in entry.asset.lower():
            extra_terms = terms
            break
    base_score = _exposure_weight(entry.exposure) * _position_weight(entry.position)
    direct_link = any(_asset_matches(entry.asset, asset) for asset in related_assets)
    term_match = _contains_any(text_haystack, required_terms) or (extra_terms and _contains_any(text_haystack, extra_terms))
    if direct_link:
        return base_score, DIRECT_PORTFOLIO_LINK_BONUS
    if term_match:
        return base_score * INDIRECT_RELEVANCE_MULTIPLIER, 0.0
    return 0.0, 0.0


def _book_relevance(
    positions: list[PositionEntry],
    text: str,
    related_assets: tuple[str, ...] = (),
) -> tuple[float, str, str, str, float]:
    scored = [
        (entry, relevance, direct_bonus)
        for entry in positions
        for relevance, direct_bonus in [_position_relevance(entry, text, related_assets)]
        if relevance > 0
    ]
    if not scored:
        return (0.5, "General macro", "", "", 0.0)
    entry, score, direct_bonus = max(scored, key=lambda item: (item[1] + item[2], item[2], item[1]))
    return (score, entry.asset, entry.position, entry.exposure, direct_bonus)


def _evidence_for_assets(rows_by_asset: dict[str, MarketRow], assets: tuple[str, ...]) -> tuple[str, ...]:
    evidence: list[str] = []
    for asset in assets:
        row = rows_by_asset.get(asset)
        if row is None or not row.change:
            continue
        date_part = f" as of {row.as_of}" if row.as_of else ""
        evidence.append(f"{asset}: {row.change}{date_part}; {row.so_what}")
    return tuple(evidence[:3])


def _candidate_score(entry: PositionEntry, rows_by_asset: dict[str, MarketRow], related_assets: tuple[str, ...]) -> float:
    evidence_score = sum(_change_score(rows_by_asset[asset].change) for asset in related_assets if asset in rows_by_asset)
    return evidence_score * _exposure_weight(entry.exposure) * _position_weight(entry.position)


def _event_importance(event: CalendarEvent) -> float:
    text = f"{event.session} {event.event}".lower()
    if _contains_any(text, ("cpi", "ppi", "pce", "payroll", "nfp", "fomc", "fed", "ecb", "boj", "rate", "press conference")):
        base = 3.2
    elif _contains_any(text, ("gdp", "pmi", "ism", "retail", "m2", "current account", "trade balance", "unemployment")):
        base = 2.2
    else:
        base = 1.1
    if event.status == "Live":
        base += 0.4
    elif event.status == "*":
        base -= 0.2
    if event.consensus and event.consensus.lower() != "n/a":
        base += 0.2
    return max(base, 0.5)


def _event_profile(event: CalendarEvent) -> tuple[str, tuple[str, ...], tuple[str, ...], str]:
    text = f"{event.session} {event.event}".lower()
    if _contains_any(text, ("cpi", "ppi", "pce", "inflation")):
        label = "US Inflation Event Risk" if "usd" in text or event.session == "US" else "Inflation Event Risk"
        return (label, ("US 10Y yield", "DXY", "Gold", "S&P 500"), ("inflation", "cpi", "ppi", "pce", "rates"), "inflation")
    if _contains_any(text, ("fed", "fomc", "usd rate")):
        return ("Fed Policy Event Risk", ("US 10Y yield", "DXY", "Gold"), ("fed", "fomc", "rates", "treasury"), "rates")
    if _contains_any(text, ("ecb", "eur", "refinancing rate")):
        return ("ECB Policy Event Risk", ("EUR/USD", "DXY", "Euro Stoxx 50"), ("ecb", "eur", "euro", "rates"), "policy")
    if _contains_any(text, ("boj", "jpy", "japan")):
        return ("Japan Policy Event Risk", ("USD/JPY", "Japan 10Y yield"), ("boj", "jpy", "yen", "japan"), "fx")
    if _contains_any(text, ("cny", "china", "m2", "pmi")):
        return ("China Data Watch", ("China internet / tech basket", "S&P 500", "Brent oil"), ("china", "cny", "pmi", "m2"), "china")
    if _contains_any(text, ("gdp", "growth", "retail", "ism", "pmi")):
        return ("Growth Data Watch", ("S&P 500", "US 10Y yield", "DXY"), ("growth", "gdp", "pmi", "risk"), "growth")
    return ("Calendar Event Risk", ("US 10Y yield", "DXY", "S&P 500"), ("calendar", "event", event.event.lower()), "calendar")


def _calendar_evidence(event: CalendarEvent) -> tuple[str, ...]:
    consensus = f"; consensus {event.consensus}" if event.consensus and event.consensus.lower() != "n/a" else ""
    timing = f"{event.event_date} {event.time}".strip()
    return (f"Calendar: {event.event} at {timing}{consensus}; {event.why_it_matters}",)


def _calendar_candidates(data: BriefData, positions: list[PositionEntry]) -> list[TopicCandidate]:
    candidates: list[TopicCandidate] = []
    for event in data.calendar:
        title, related_assets, required_terms, group = _event_profile(event)
        event_text = f"{event.session} {event.event} {event.why_it_matters}"
        relevance, portfolio_asset, position, exposure, direct_bonus = _book_relevance(
            positions,
            event_text,
            related_assets,
        )
        importance = _event_importance(event)
        score = importance + relevance + direct_bonus
        if score < 2.5:
            continue
        candidates.append(
            TopicCandidate(
                title=title,
                origin="calendar",
                portfolio_asset=portfolio_asset,
                position=position,
                exposure=exposure,
                related_assets=related_assets,
                evidence=_calendar_evidence(event),
                required_terms=required_terms,
                group=group,
                score=score,
                source_label="Forex Factory / Fair Economy calendar",
                link=event.link,
                score_components=(
                    ("event_importance", importance),
                    ("book_relevance", relevance),
                    ("direct_portfolio_link", direct_bonus),
                ),
            )
        )
    return candidates


def _theme_source_score(item: ThemeItem) -> float:
    source = item.source.lower()
    if any(name in source for name in ("liberty street", "bank underground", "fred", "bis", "imf", "federal reserve")):
        base = 2.2
    elif any(name in source for name in ("reuters", "financial times", "bloomberg", "wall street journal", "economist")):
        base = 2.0
    else:
        base = 1.2
    depth = item.source_depth.lower()
    if "full" in depth:
        base += 0.8
    elif "rss" in depth:
        base += 0.3
    elif "snippet" in depth:
        base -= 0.1
    return base


def _theme_profile(item: ThemeItem) -> tuple[str, tuple[str, ...], tuple[str, ...], str]:
    text = f"{item.title} {item.summary} {item.book_impact}".lower()
    if _contains_any(text, ("inflation expectation", "inflation", "housing")):
        return ("Inflation Expectations Signal", ("US 10Y yield", "Gold", "DXY"), ("inflation", "expectations", "rates", "gold"), "inflation")
    if _contains_any(text, ("credit", "loan", "borrower", "funding")):
        return ("Credit Conditions Signal", ("S&P 500", "DXY", "US 10Y yield"), ("credit", "funding", "borrowers", "risk"), "credit")
    if _contains_any(text, ("rate", "yield", "duration", "term premium")):
        return ("Rates Research Signal", ("US 10Y yield", "Gold", "DXY"), ("rates", "yield", "duration", "term premium"), "rates")
    if _contains_any(text, ("dollar", "currency", "fx")):
        return ("Dollar Research Signal", ("DXY", "EUR/USD", "USD/JPY"), ("dollar", "currency", "fx", "dxy"), "fx")
    return ("Theme Radar Signal", ("S&P 500", "US 10Y yield", "DXY"), ("theme", "research", "risk"), "theme")


def _shorten(text: str, limit: int = 220) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip(" ,;:") + "."


def _theme_candidates(data: BriefData, positions: list[PositionEntry]) -> list[TopicCandidate]:
    candidates: list[TopicCandidate] = []
    for item in data.theme_radar:
        title, related_assets, required_terms, group = _theme_profile(item)
        theme_text = f"{item.title} {item.summary} {item.book_impact}"
        relevance, portfolio_asset, position, exposure, direct_bonus = _book_relevance(
            positions,
            theme_text,
            related_assets,
        )
        source_score = _theme_source_score(item)
        freshness_score = 0.6
        score = source_score + relevance + direct_bonus + freshness_score
        if score < 3.0:
            continue
        candidates.append(
            TopicCandidate(
                title=title,
                origin="theme",
                portfolio_asset=portfolio_asset,
                position=position,
                exposure=exposure,
                related_assets=related_assets,
                evidence=(f"Theme Radar: {item.title} from {item.source}; {_shorten(item.summary)}",),
                required_terms=required_terms,
                group=group,
                score=score,
                source_label=item.source,
                link=item.link,
                score_components=(
                    ("source_quality", source_score),
                    ("book_relevance", relevance),
                    ("direct_portfolio_link", direct_bonus),
                    ("freshness", freshness_score),
                ),
            )
        )
    return candidates


def _candidate_to_prompt_dict(candidate: TopicCandidate) -> dict[str, object]:
    return {
        "title": candidate.title,
        "origin": candidate.origin,
        "portfolio_asset": candidate.portfolio_asset,
        "position": candidate.position,
        "exposure": candidate.exposure,
        "evidence": list(candidate.evidence),
        "required_terms": list(candidate.required_terms),
        "source_label": candidate.source_label,
        "link": candidate.link,
        "score": round(candidate.score, 3),
        "score_components": {name: round(value, 3) for name, value in candidate.score_components},
    }


def _select_chart_asset(candidate: TopicCandidate, data: BriefData) -> str | None:
    for asset in candidate.related_assets:
        if asset in data.market_series and len(data.market_series[asset]) >= 5:
            return asset
    if data.chart_series:
        return "USD/JPY"
    return None


def _chart_y_label(asset: str) -> str:
    if "yield" in asset.lower():
        return "Yield (%)"
    if asset in {"Gold", "Brent oil", "WTI oil", "China internet / tech basket"}:
        return "Price"
    if asset in {"VIX", "S&P 500", "Euro Stoxx 50", "DXY"}:
        return "Index"
    return "Spot"


def _chart_caption(asset: str, rows_by_asset: dict[str, MarketRow], topic_title: str) -> str:
    row = rows_by_asset.get(asset)
    if row is None or not row.so_what:
        return f"{asset} is the clearest available market series for {topic_title.lower()}."
    return row.so_what


def select_portfolio_topics(data: BriefData, *, run_date: date, portfolio_path: Path, limit: int = 3) -> BriefData:
    entries = read_position_entries(portfolio_path)
    positions = active_positions(entries, run_date)
    if not positions:
        return data

    rows_by_asset = {row.asset: row for row in data.market_rows}
    candidates: list[TopicCandidate] = []
    for entry in positions:
        title, related_assets, required_terms, group = _position_profile(entry)
        evidence = _evidence_for_assets(rows_by_asset, related_assets)
        if not evidence:
            continue
        score = _candidate_score(entry, rows_by_asset, related_assets) + DIRECT_PORTFOLIO_LINK_BONUS
        if score <= 0:
            continue
        candidates.append(
            TopicCandidate(
                title=title,
                origin="market",
                portfolio_asset=entry.asset,
                position=entry.position,
                exposure=entry.exposure,
                related_assets=related_assets,
                evidence=evidence,
                required_terms=required_terms,
                group=group,
                score=score,
                score_components=(
                    ("market_move", sum(_change_score(rows_by_asset[asset].change) for asset in related_assets if asset in rows_by_asset)),
                    ("exposure", _exposure_weight(entry.exposure)),
                    ("position_weight", _position_weight(entry.position)),
                    ("direct_portfolio_link", DIRECT_PORTFOLIO_LINK_BONUS),
                ),
            )
        )

    candidates.extend(_calendar_candidates(data, positions))
    candidates.extend(_theme_candidates(data, positions))

    if not candidates:
        return data

    selected: list[TopicCandidate] = []
    used_groups: set[str] = set()
    for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
        if candidate.group in used_groups and len(candidates) - len(selected) > 1:
            continue
        selected.append(candidate)
        used_groups.add(candidate.group)
        if len(selected) == limit:
            break
    if len(selected) < limit:
        for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
            if candidate in selected:
                continue
            selected.append(candidate)
            if len(selected) == limit:
                break

    chart_asset = _select_chart_asset(selected[0], data)
    if chart_asset and chart_asset in data.market_series:
        chart_series = list(data.market_series[chart_asset])
    else:
        chart_asset = "USD/JPY"
        chart_series = data.chart_series
    chart_source_label, chart_source_url = CHART_SOURCE_BY_ASSET.get(
        chart_asset,
        (f"{chart_asset} chart data", ""),
    )

    selection_note = (
        "Topic selection ranks market moves, calendar events, and Theme Radar/news signals using active portfolio rows, "
        "direct portfolio links, exposure labels, source/event importance, freshness, and simple diversification rules before Gemini writes the narrative."
    )
    return replace(
        data,
        chart_series=chart_series,
        chart_title=f"{chart_asset}: 3-Month Trend",
        chart_y_label=_chart_y_label(chart_asset),
        chart_caption=_chart_caption(chart_asset, rows_by_asset, selected[0].title),
        chart_source_label=chart_source_label,
        chart_source_url=chart_source_url,
        topic_candidates=[_candidate_to_prompt_dict(candidate) for candidate in selected],
        three_thing_titles=[candidate.title for candidate in selected],
        assumptions=[*data.assumptions, selection_note],
        data_sources=[*data.data_sources, "portfolio_topic_selection"],
    )
