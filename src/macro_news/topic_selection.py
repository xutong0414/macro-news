from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from .feedback import feedback_adjustment_for_text, read_feedback_adjustments
from .portfolio import PositionEntry, active_positions, read_position_entries
from .sample_data import BriefData, CalendarEvent, MarketRow, ThemeItem


@dataclass(frozen=True)
class TopicCandidate:
    title: str
    origin: str
    portfolio_asset: str
    position: str
    exposure: str
    significance: str
    related_assets: tuple[str, ...]
    evidence: tuple[str, ...]
    required_terms: tuple[str, ...]
    group: str
    score: float
    source_label: str = ""
    link: str = ""
    score_components: tuple[tuple[str, float], ...] = ()
    narrative_guidance: str = ""
    avoid_claims: tuple[str, ...] = ()


CHART_SOURCE_BY_ASSET = {
    "S&P 500": ("Yahoo Finance S&P 500 chart data", "https://finance.yahoo.com/quote/%5EGSPC/"),
    "Nasdaq 100": ("Yahoo Finance Nasdaq 100 chart data", "https://finance.yahoo.com/quote/%5ENDX/"),
    "US AI semiconductors basket": ("Yahoo Finance SOXX chart data", "https://finance.yahoo.com/quote/SOXX/"),
    "US data-center power basket": ("Yahoo Finance XLU chart data", "https://finance.yahoo.com/quote/XLU/"),
    "Euro Stoxx 50": ("Yahoo Finance Euro Stoxx 50 chart data", "https://finance.yahoo.com/quote/%5ESTOXX50E/"),
    "US 10Y yield": ("Yahoo Finance US 10Y chart data", "https://finance.yahoo.com/quote/%5ETNX/"),
    "China internet / tech basket": ("Yahoo Finance KWEB chart data", "https://finance.yahoo.com/quote/KWEB/"),
    "DXY": ("Yahoo Finance DXY chart data", "https://finance.yahoo.com/quote/DX-Y.NYB/"),
    "EUR/USD": ("Frankfurter EUR/USD daily reference rates", "https://frankfurter.dev/"),
    "USD/JPY": ("Frankfurter USD/JPY daily reference rates", "https://frankfurter.dev/"),
    "Gold": ("Yahoo Finance gold futures chart data", "https://finance.yahoo.com/quote/GC=F/"),
    "Brent oil": ("Yahoo Finance Brent oil futures chart data", "https://finance.yahoo.com/quote/BZ=F/"),
    "WTI oil": ("Yahoo Finance WTI oil futures chart data", "https://finance.yahoo.com/quote/CL=F/"),
    "Copper": ("Yahoo Finance copper futures chart data", "https://finance.yahoo.com/quote/HG=F/"),
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


def _significance_weight(significance: str) -> float:
    return {
        "high": 1.25,
        "medium": 1.0,
        "low": 0.85,
    }.get(significance.lower(), 1.0)


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
    if "semiconductor" in key or ("ai" in key and "chip" in key):
        return (
            "AI Semiconductor Cycle",
            ("US AI semiconductors basket", "Nasdaq 100", "S&P 500", "US 10Y yield", "VIX"),
            ("ai", "artificial intelligence", "semiconductor", "chip", "gpu", "capex", "data center"),
            "ai_equity",
        )
    if "data center power" in key or "utility" in key or "power basket" in key:
        return (
            "AI Power Bottleneck",
            ("US data-center power basket", "Copper", "US 10Y yield", "S&P 500"),
            ("ai", "artificial intelligence", "data center", "datacenter", "power", "electricity", "grid", "utilities"),
            "ai_power",
        )
    if "nasdaq" in key or ("ai" in key and "equity" in key):
        return (
            "US AI Equity Cycle",
            ("Nasdaq 100", "US AI semiconductors basket", "S&P 500", "US 10Y yield", "VIX"),
            ("ai", "artificial intelligence", "nasdaq", "growth", "semiconductor", "software", "capex"),
            "ai_equity",
        )
    if "copper" in key:
        return (
            "Copper And Electrification Demand",
            ("Copper", "China internet / tech basket", "US data-center power basket", "Brent oil"),
            ("copper", "electrification", "grid", "industrial", "china", "ai infrastructure"),
            "copper",
        )
    if "defense" in key or "rearmament" in key:
        return (
            "Defense And Fiscal Security Theme",
            ("Euro Stoxx 50", "US 10Y yield", "DXY"),
            ("defense", "rearmament", "security", "nato", "fiscal", "europe"),
            "defense",
        )
    if "stablecoin" in key or "crypto infrastructure" in key:
        return (
            "Stablecoin And Crypto Plumbing",
            ("BTC", "DXY", "US 10Y yield"),
            ("stablecoin", "crypto", "token", "digital dollar", "payments", "btc"),
            "crypto",
        )
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
        "nasdaq": ("nasdaq", "growth", "ai", "artificial intelligence", "semiconductor", "software"),
        "semiconductor": ("ai", "artificial intelligence", "semiconductor", "chip", "gpu", "hbm", "capex"),
        "data center power": ("ai", "artificial intelligence", "data center", "datacenter", "power", "electricity", "grid", "utilities"),
        "copper": ("copper", "electrification", "grid", "industrial", "china"),
        "defense": ("defense", "rearmament", "nato", "security", "fiscal", "europe"),
        "stablecoin": ("stablecoin", "crypto", "payments", "token", "digital dollar", "btc"),
    }
    entry_key = _clean_key(entry.asset)
    extra_terms: tuple[str, ...] = ()
    for key, terms in keyword_sets.items():
        if key.replace("/", " ") in entry_key or key in entry.asset.lower():
            extra_terms = terms
            break
    base_score = _exposure_weight(entry.exposure) * _position_weight(entry.position) * _significance_weight(entry.significance)
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
) -> tuple[float, str, str, str, str, float]:
    scored = [
        (entry, relevance, direct_bonus)
        for entry in positions
        for relevance, direct_bonus in [_position_relevance(entry, text, related_assets)]
        if relevance > 0
    ]
    if not scored:
        return (0.5, "General macro", "", "", "", 0.0)
    entry, score, direct_bonus = max(scored, key=lambda item: (item[1] + item[2], item[2], item[1]))
    return (score, entry.asset, entry.position, entry.exposure, entry.significance, direct_bonus)


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
    return evidence_score * _exposure_weight(entry.exposure) * _position_weight(entry.position) * _significance_weight(entry.significance)


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
        relevance, portfolio_asset, position, exposure, significance, direct_bonus = _book_relevance(
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
                significance=significance,
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
                    ("significance", _significance_weight(significance)),
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
    if "article text" in depth or "full" in depth:
        base += 0.8
    elif "article metadata" in depth:
        base += 0.5
    elif "rss" in depth:
        base += 0.3
    elif "snippet" in depth:
        base -= 0.1
    return base


def _theme_profile(item: ThemeItem) -> tuple[str, tuple[str, ...], tuple[str, ...], str]:
    text = f"{item.title} {item.summary} {item.book_impact}".lower()
    padded = f" {text} "
    if _contains_any(padded, (" electricity", " power grid", " utilities", " grid bottleneck", " power demand")) and _contains_any(
        padded,
        (" ai ", " artificial intelligence", " semiconductor", " chip", " gpu", " data center", " datacenter"),
    ):
        return (
            "AI Power Bottleneck",
            ("US data-center power basket", "Copper", "Nasdaq 100", "US 10Y yield"),
            ("ai", "data center", "power", "grid", "electricity"),
            "ai_power",
        )
    if _contains_any(padded, (" semiconductor", " chip", " gpu", " hbm", " ai capex")):
        return (
            "AI Semiconductor Cycle",
            ("US AI semiconductors basket", "Nasdaq 100", "S&P 500", "VIX"),
            ("ai", "semiconductor", "chip", "gpu", "capex"),
            "ai_equity",
        )
    if _contains_any(padded, (" artificial intelligence", " ai ", " hyperscaler", " software", " cloud")):
        return (
            "US AI Equity Cycle",
            ("Nasdaq 100", "US AI semiconductors basket", "S&P 500", "US 10Y yield"),
            ("ai", "artificial intelligence", "growth", "software", "cloud"),
            "ai_equity",
        )
    if _contains_any(text, ("defense", "rearmament", "nato", "security spending")):
        return (
            "Defense And Fiscal Security Theme",
            ("Euro Stoxx 50", "US 10Y yield", "DXY"),
            ("defense", "rearmament", "nato", "security", "fiscal"),
            "defense",
        )
    if _contains_any(text, ("stablecoin", "tokenized", "tokenised", "digital dollar", "crypto payments")):
        return (
            "Stablecoin And Crypto Plumbing",
            ("BTC", "DXY", "US 10Y yield"),
            ("stablecoin", "token", "crypto", "payments", "dollar"),
            "crypto",
        )
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


def _direction_from_change(value: str) -> str:
    normalized = value.strip().lower().replace("−", "-")
    match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*(bp|%)?", normalized)
    if match is None:
        return ""
    try:
        amount = float(match.group(1))
    except ValueError:
        return ""
    unit = match.group(2) or ""
    flat_threshold = 0.5 if unit == "bp" else 0.05
    if abs(amount) <= flat_threshold:
        return "flat"
    return "up" if amount > 0 else "down"


def _evidence_direction(evidence: tuple[str, ...], asset: str) -> str:
    prefix = f"{asset}:"
    for item in evidence:
        if not item.startswith(prefix):
            continue
        change_text = item.removeprefix(prefix).split(";", 1)[0].split(" as of ", 1)[0]
        return _direction_from_change(change_text)
    return ""


def _direction_phrase(asset: str, direction: str) -> str:
    if direction == "up":
        return f"{asset} is up"
    if direction == "down":
        return f"{asset} is down"
    if direction == "flat":
        return f"{asset} is roughly flat"
    return ""


def _row_direction(rows_by_asset: dict[str, MarketRow], asset: str) -> str:
    row = rows_by_asset.get(asset)
    if row is None:
        return ""
    return _direction_from_change(row.change)


def _global_dashboard_guardrails(rows_by_asset: dict[str, MarketRow]) -> tuple[str, tuple[str, ...]]:
    guidance: list[str] = []
    avoid: list[str] = []

    dxy_direction = _row_direction(rows_by_asset, "DXY")
    if dxy_direction == "up":
        guidance.append("Global dashboard guardrail: DXY is up, so broad dollar pressure is firmer, not easier.")
        avoid.append("Do not say broad dollar pressure eased, dollar pressure softened, or dollar funding conditions loosened.")
    elif dxy_direction == "down":
        guidance.append("Global dashboard guardrail: DXY is down, so broad dollar pressure is softer, not tighter.")
        avoid.append("Do not say broad dollar pressure tightened because of DXY.")

    vix_direction = _row_direction(rows_by_asset, "VIX")
    if vix_direction == "up":
        guidance.append("Global dashboard guardrail: VIX is up, so volatility or hedging stress is firmer.")
        avoid.append("Do not say hedging stress faded or volatility eased because of VIX.")
    elif vix_direction == "down":
        guidance.append("Global dashboard guardrail: VIX is down, so volatility stress has eased.")
        avoid.append("Do not say volatility or defensive stress increased because of VIX.")

    oil_directions = tuple(
        direction
        for direction in (_row_direction(rows_by_asset, "Brent oil"), _row_direction(rows_by_asset, "WTI oil"))
        if direction
    )
    if "up" in oil_directions:
        guidance.append("Global dashboard guardrail: cited oil is up, so oil is not easing inflation pressure.")
        avoid.append("Do not say oil eased inflation pressure when the cited oil row is up.")
    elif oil_directions and all(direction == "down" for direction in oil_directions):
        guidance.append("Global dashboard guardrail: cited oil is down, so oil is easing inflation pressure.")
        avoid.append("Do not say oil increased inflation pressure when the cited oil row is down.")

    return " ".join(dict.fromkeys(guidance)), tuple(dict.fromkeys(avoid))


def _candidate_narrative_guardrails(
    candidate: TopicCandidate,
    rows_by_asset: dict[str, MarketRow] | None = None,
) -> tuple[str, tuple[str, ...]]:
    rows_by_asset = rows_by_asset or {}
    directions = {
        asset: _evidence_direction(candidate.evidence, asset)
        for asset in candidate.related_assets
    }
    guidance: list[str] = []
    avoid: list[str] = []
    title_key = _clean_key(candidate.title)
    portfolio_key = _clean_key(candidate.portfolio_asset)
    position_key = _clean_key(candidate.position)

    dxy_direction = directions.get("DXY", "") or _row_direction(rows_by_asset, "DXY")
    us_yield_direction = directions.get("US 10Y yield", "") or _row_direction(rows_by_asset, "US 10Y yield")
    jpy_direction = directions.get("USD/JPY", "") or _row_direction(rows_by_asset, "USD/JPY")
    japan_yield_direction = directions.get("Japan 10Y yield", "") or _row_direction(rows_by_asset, "Japan 10Y yield")
    gold_direction = directions.get("Gold", "") or _row_direction(rows_by_asset, "Gold")
    vix_direction = directions.get("VIX", "") or _row_direction(rows_by_asset, "VIX")
    spx_direction = directions.get("S&P 500", "") or _row_direction(rows_by_asset, "S&P 500")
    brent_direction = directions.get("Brent oil", "") or _row_direction(rows_by_asset, "Brent oil")
    wti_direction = directions.get("WTI oil", "") or _row_direction(rows_by_asset, "WTI oil")

    if "em debt" in title_key or "em debt" in portfolio_key or "emerging market" in title_key:
        if dxy_direction == "up":
            guidance.append("DXY is up, so treat dollar pressure as tighter funding for EM debt.")
            avoid.append("Do not say stronger DXY eases dollar pressure or helps EM debt.")
        elif dxy_direction == "down":
            guidance.append("DXY is down, so dollar pressure is easing for EM debt unless another fact offsets it.")
            avoid.append("Do not say dollar funding pressure tightened because of DXY.")
        if us_yield_direction == "up":
            guidance.append("US 10Y yield is up, which pressures EM duration.")
            avoid.append("Do not say higher US yields help EM debt.")
        elif us_yield_direction == "down":
            guidance.append("US 10Y yield is down, which gives EM duration some relief.")
        if spx_direction == "down":
            guidance.append("S&P 500 is down, so risk tone is a headwind for EM debt.")
        elif spx_direction == "up":
            guidance.append("S&P 500 is up, so equity tone is a partial support for EM debt.")

    if "usd jpy" in title_key or "usd jpy" in portfolio_key:
        if jpy_direction == "up":
            guidance.append("USD/JPY is up, so the long USD/JPY position is working, but intervention or yen-reversal risk should be monitored.")
            avoid.append("Do not frame USD/JPY gains, stronger DXY, or higher US yields as direct pressure on a long USD/JPY position.")
        elif jpy_direction == "down":
            guidance.append("USD/JPY is down, so the long USD/JPY position is under pressure.")
        if japan_yield_direction == "up":
            guidance.append("Japan 10Y yield is up; mention Japan-rate pressure separately and do not infer carry or spread direction.")
            avoid.append("Do not say higher Japanese yields reinforce carry unless a carry or spread calculation is provided.")

    if "gold" in title_key or "gold" in portfolio_key:
        if gold_direction == "up":
            guidance.append("Gold is up, so the gold overweight is supported by the price move.")
        elif gold_direction == "down":
            guidance.append("Gold is down, so the gold overweight is pressured by the price move.")
            avoid.append("Do not say a falling gold price helps the gold overweight.")
        if dxy_direction == "up":
            guidance.append("DXY is up, which is a headwind for gold.")
            avoid.append("Do not say dollar pressure eased when DXY is up.")
        elif dxy_direction == "down":
            guidance.append("DXY is down, which gives gold some dollar relief.")
        if us_yield_direction == "up":
            guidance.append("US 10Y yield is up, which is rate pressure on gold.")
        elif us_yield_direction == "down":
            guidance.append("US 10Y yield is down, which eases rate pressure on gold.")

    if "dollar" in title_key or "eur usd" in title_key:
        if dxy_direction == "up":
            guidance.append("DXY is up, so broad dollar pressure is firmer.")
            avoid.append("Do not say broad dollar pressure eased or dollar funding loosened.")
        elif dxy_direction == "down":
            guidance.append("DXY is down, so broad dollar pressure is softer.")
            avoid.append("Do not say broad dollar pressure tightened because of DXY.")

    if "oil" in title_key or "inflation" in title_key:
        oil_directions = tuple(direction for direction in (brent_direction, wti_direction) if direction)
        if "up" in oil_directions:
            guidance.append("Oil is up in the provided evidence, so oil is adding to inflation pressure.")
            avoid.append("Do not say oil eased inflation pressure when the cited oil row is up.")
        elif oil_directions and all(direction == "down" for direction in oil_directions):
            guidance.append("Oil is down in the provided evidence, so oil is easing inflation pressure.")
            avoid.append("Do not say oil increased inflation pressure when the cited oil row is down.")

    if "volatility" in title_key or "risk tone" in title_key or "equity" in title_key:
        if vix_direction == "up":
            guidance.append("VIX is up, so hedging stress or volatility demand is firmer.")
            avoid.append("Do not say hedging stress faded when VIX is up.")
        elif vix_direction == "down":
            guidance.append("VIX is down, so volatility stress has eased.")
            avoid.append("Do not say defensive stress increased because of VIX.")
        if spx_direction == "up":
            guidance.append("S&P 500 is up, so US equity tone is supportive unless another fact offsets it.")
        elif spx_direction == "down":
            guidance.append("S&P 500 is down, so US equity tone is defensive.")
    if "s p 500" in portfolio_key and "underweight" in position_key:
        if spx_direction == "up":
            guidance.append("Because the book is underweight S&P 500, a rising S&P 500 is a headwind for that position even if it supports broad risk appetite.")
            avoid.append("Do not say a rising S&P 500 is a tailwind, benefit, or support for the underweight S&P 500 position.")
        elif spx_direction == "down":
            guidance.append("Because the book is underweight S&P 500, a falling S&P 500 supports that position even though it signals weaker risk tone.")

    if candidate.origin == "calendar" and ("event risk" in title_key or "policy event" in title_key):
        guidance.append("This is an event-risk topic; unless the evidence states the actual outcome, frame the effect as a catalyst to watch rather than a realized market reaction.")
        avoid.append("Do not infer the event outcome or market reaction beyond the calendar facts.")

    compact_guidance = " ".join(dict.fromkeys(item for item in guidance if item))
    compact_avoid = tuple(dict.fromkeys(item for item in avoid if item))
    return compact_guidance, compact_avoid


def _theme_candidates(data: BriefData, positions: list[PositionEntry]) -> list[TopicCandidate]:
    candidates: list[TopicCandidate] = []
    for item in data.theme_radar:
        title, related_assets, required_terms, group = _theme_profile(item)
        theme_text = f"{item.title} {item.summary} {item.book_impact}"
        relevance, portfolio_asset, position, exposure, significance, direct_bonus = _book_relevance(
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
                significance=significance,
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
                    ("significance", _significance_weight(significance)),
                    ("freshness", freshness_score),
                ),
            )
        )
    return candidates


def _candidate_to_prompt_dict(
    candidate: TopicCandidate,
    rows_by_asset: dict[str, MarketRow] | None = None,
) -> dict[str, object]:
    specific_guidance, specific_avoid_claims = _candidate_narrative_guardrails(candidate, rows_by_asset)
    narrative_guidance = " ".join(
        item
        for item in (candidate.narrative_guidance, specific_guidance)
        if item
    )
    avoid_claims = tuple(dict.fromkeys((*candidate.avoid_claims, *specific_avoid_claims)))
    return {
        "title": candidate.title,
        "origin": candidate.origin,
        "portfolio_asset": candidate.portfolio_asset,
        "position": candidate.position,
        "exposure": candidate.exposure,
        "significance": candidate.significance,
        "evidence": list(candidate.evidence),
        "required_terms": list(candidate.required_terms),
        "source_label": candidate.source_label,
        "link": candidate.link,
        "score": round(candidate.score, 3),
        "score_components": {name: round(value, 3) for name, value in candidate.score_components},
        "narrative_guidance": narrative_guidance,
        "avoid_claims": list(avoid_claims),
    }


def _component_label(name: str) -> str:
    return {
        "market_move": "market move size",
        "exposure": "portfolio exposure",
        "significance": "portfolio significance",
        "position_weight": "position stance",
        "direct_portfolio_link": "direct portfolio link",
        "event_importance": "event importance",
        "book_relevance": "book relevance",
        "source_quality": "source quality/depth",
        "freshness": "freshness",
        "reader_feedback": "reader feedback",
    }.get(name, name.replace("_", " "))


def _selection_driver_text(candidate: TopicCandidate) -> str:
    positive_components = [
        (name, value)
        for name, value in candidate.score_components
        if value > 0 and name not in {"position_weight"}
    ]
    top_components = sorted(positive_components, key=lambda item: item[1], reverse=True)[:3]
    drivers = ", ".join(f"{_component_label(name)} {value:.2f}" for name, value in top_components)
    if not drivers:
        drivers = "available evidence and portfolio relevance"
    if candidate.portfolio_asset and candidate.portfolio_asset != "General macro":
        return f"Ranked from {candidate.origin} evidence because {drivers}; linked to {candidate.portfolio_asset} ({candidate.position or 'watch'}, exposure={candidate.exposure or 'n/a'}, significance={candidate.significance or 'n/a'})."
    return f"Ranked from {candidate.origin} evidence because {drivers}; no direct active-position link dominated."


def _selection_report(selected: list[TopicCandidate]) -> list[dict[str, object]]:
    report: list[dict[str, object]] = []
    for rank, candidate in enumerate(selected, 1):
        report.append(
            {
                "rank": rank,
                "title": candidate.title,
                "origin": candidate.origin,
                "portfolio_asset": candidate.portfolio_asset,
                "position": candidate.position,
                "exposure": candidate.exposure,
                "significance": candidate.significance,
                "score": round(candidate.score, 3),
                "score_components": {name: round(value, 3) for name, value in candidate.score_components},
                "why_selected": _selection_driver_text(candidate),
                "source_label": candidate.source_label,
                "link": candidate.link,
                "evidence": list(candidate.evidence),
            }
        )
    return report


def _candidate_feedback_text(candidate: TopicCandidate) -> str:
    return " ".join(
        [
            candidate.title,
            candidate.origin,
            candidate.portfolio_asset,
            candidate.position,
            candidate.exposure,
            candidate.significance,
            candidate.source_label,
            " ".join(candidate.related_assets),
            " ".join(candidate.evidence),
        ]
    )


def _apply_reader_feedback(candidates: list[TopicCandidate], feedback_path: Path) -> tuple[list[TopicCandidate], int]:
    adjustments = read_feedback_adjustments(feedback_path)
    if not adjustments:
        return candidates, 0
    adjusted: list[TopicCandidate] = []
    matched_count = 0
    for candidate in candidates:
        adjustment, matched_items = feedback_adjustment_for_text(_candidate_feedback_text(candidate), adjustments)
        if adjustment == 0:
            adjusted.append(candidate)
            continue
        matched_count += len(matched_items)
        adjusted.append(
            replace(
                candidate,
                score=max(candidate.score + adjustment, 0.0),
                score_components=(
                    *candidate.score_components,
                    ("reader_feedback", adjustment),
                ),
            )
        )
    return adjusted, matched_count


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
    if asset in {"Gold", "Brent oil", "WTI oil", "China internet / tech basket", "US AI semiconductors basket", "US data-center power basket", "Copper"}:
        return "Price"
    if asset in {"VIX", "S&P 500", "Nasdaq 100", "Euro Stoxx 50", "DXY"}:
        return "Index"
    return "Spot"


def _chart_caption(asset: str, rows_by_asset: dict[str, MarketRow], topic_title: str) -> str:
    row = rows_by_asset.get(asset)
    if row is None or not row.so_what:
        return f"{asset} is the clearest available market series for {topic_title.lower()}."
    return row.so_what


def select_portfolio_topics(
    data: BriefData,
    *,
    run_date: date,
    portfolio_path: Path,
    feedback_path: Path | None = None,
    limit: int = 3,
) -> BriefData:
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
                significance=entry.significance,
                related_assets=related_assets,
                evidence=evidence,
                required_terms=required_terms,
                group=group,
                score=score,
                score_components=(
                    ("market_move", sum(_change_score(rows_by_asset[asset].change) for asset in related_assets if asset in rows_by_asset)),
                    ("exposure", _exposure_weight(entry.exposure)),
                    ("significance", _significance_weight(entry.significance)),
                    ("position_weight", _position_weight(entry.position)),
                    ("direct_portfolio_link", DIRECT_PORTFOLIO_LINK_BONUS),
                ),
            )
        )

    candidates.extend(_calendar_candidates(data, positions))
    candidates.extend(_theme_candidates(data, positions))
    feedback_match_count = 0
    if feedback_path is not None:
        candidates, feedback_match_count = _apply_reader_feedback(candidates, feedback_path)

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

    global_guidance, global_avoid_claims = _global_dashboard_guardrails(rows_by_asset)
    selected_with_guardrails = [
        replace(
            candidate,
            narrative_guidance=global_guidance,
            avoid_claims=global_avoid_claims,
        )
        for candidate in selected
    ]

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
    feedback_note = (
        "Reader feedback input adjusted topic scores from the local feedback CSV; this is local preference memory, not model fine-tuning."
        if feedback_match_count
        else ""
    )
    return replace(
        data,
        chart_series=chart_series,
        chart_title=f"{chart_asset}: 3-Month Trend",
        chart_y_label=_chart_y_label(chart_asset),
        chart_caption=_chart_caption(chart_asset, rows_by_asset, selected[0].title),
        chart_source_label=chart_source_label,
        chart_source_url=chart_source_url,
        topic_candidates=[_candidate_to_prompt_dict(candidate, rows_by_asset) for candidate in selected_with_guardrails],
        topic_selection_report=_selection_report(selected),
        three_thing_titles=[candidate.title for candidate in selected],
        assumptions=[*data.assumptions, selection_note, *([feedback_note] if feedback_note else [])],
        data_sources=[*data.data_sources, "portfolio_topic_selection", *(["reader_feedback"] if feedback_match_count else [])],
    )
