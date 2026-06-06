from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import httpx

from .sample_data import BriefData, CalendarEvent

FAIRECONOMY_WEEKLY_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FAIRECONOMY_SOURCE = "faireconomy:ff_calendar_thisweek"
CALENDAR_CACHE_PATH = Path(".cache") / "calendar" / "ff_calendar_thisweek.json"

IMPACT_SCORE = {
    "High": 3,
    "Medium": 2,
    "Low": 1,
}

CURRENCY_SESSION = {
    "AUD": "Asia",
    "CNY": "Asia",
    "HKD": "Asia",
    "JPY": "Asia",
    "NZD": "Asia",
    "SGD": "Asia",
    "CHF": "Europe",
    "EUR": "Europe",
    "GBP": "Europe",
    "CAD": "US",
    "USD": "US",
}


@dataclass(frozen=True)
class CalendarDataResult:
    data: BriefData
    live_events: list[str]
    fallback_events: list[str]
    errors: dict[str, str]
    sources: list[str]


@dataclass(frozen=True)
class CalendarFetchResult:
    raw_events: list[dict]
    source: str
    refresh_error: str | None = None


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _parse_event_datetime(value: object) -> datetime:
    text = _clean_text(value)
    if not text:
        raise ValueError("missing event datetime")
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _session_for_currency(currency: str) -> str:
    return CURRENCY_SESSION.get(currency.upper(), "Global")


def _why_it_matters(title: str, currency: str, impact: str) -> str:
    lowered = title.lower()
    if any(word in lowered for word in ("cpi", "pce", "inflation", "prices")):
        return "Inflation surprise can reprice rates, dollar direction, and gold."
    if any(word in lowered for word in ("payroll", "employment", "job", "unemployment", "claims", "earnings")):
        return "Labor data can move rate expectations, yields, and dollar risk."
    if any(word in lowered for word in ("pmi", "ism", "manufacturing", "services")):
        return "Growth momentum matters for cyclicals, commodities, and risk appetite."
    if any(word in lowered for word in ("gdp", "retail sales", "trade balance", "industrial production")):
        return "Growth data can shift rates pricing and cross-asset risk tone."
    if any(word in lowered for word in ("fed", "fomc", "ecb", "boe", "boj", "rba", "speech", "speaks", "rate decision")):
        return "Policy signals can move rates and FX before hard data arrives."
    if "auction" in lowered:
        return "Auction demand is a check on term premium and duration pressure."
    if impact == "High":
        return f"High-impact {currency} event for rates, FX, and risk appetite."
    return f"{currency} macro event to keep on the radar."


def _event_identity(event: CalendarEvent) -> tuple[str, str, str]:
    return (event.session, event.time, event.event)


def _raw_event_to_calendar_event(raw_event: dict, timezone_name: str) -> CalendarEvent | None:
    impact = _clean_text(raw_event.get("impact"))
    if impact not in IMPACT_SCORE:
        return None

    title = _clean_text(raw_event.get("title"))
    currency = _clean_text(raw_event.get("country")).upper()
    if not title or not currency:
        return None

    local_time = _parse_event_datetime(raw_event.get("date")).astimezone(ZoneInfo(timezone_name))
    forecast = _clean_text(raw_event.get("forecast"))

    return CalendarEvent(
        session=_session_for_currency(currency),
        time=local_time.strftime("%b %d %H:%M %Z"),
        event=f"{currency} {title}",
        consensus=forecast or "n/a",
        why_it_matters=_why_it_matters(title, currency, impact),
    )


def _event_sort_key(raw_event: dict, run_date: date, timezone_name: str) -> tuple[int, int, int, datetime]:
    local_time = _parse_event_datetime(raw_event.get("date")).astimezone(ZoneInfo(timezone_name))
    days_from_run = (local_time.date() - run_date).days
    future_penalty = 0 if days_from_run >= 0 else 1
    impact = _clean_text(raw_event.get("impact"))
    return (future_penalty, abs(days_from_run), -IMPACT_SCORE.get(impact, 0), local_time)


def _select_events(
    raw_events: list[dict],
    *,
    run_date: date,
    timezone_name: str,
    max_events: int = 4,
    minimum_upcoming_events: int = 3,
) -> list[CalendarEvent]:
    def has_forecast_or_is_policy(raw_event: dict) -> bool:
        title = _clean_text(raw_event.get("title")).lower()
        return bool(_clean_text(raw_event.get("forecast"))) or any(word in title for word in ("speaks", "speech", "fed", "ecb", "boe", "boj", "rba"))

    groups = [
        lambda item: _is_upcoming(item, run_date, timezone_name) and _clean_text(item.get("impact")) in {"High", "Medium"},
        lambda item: _is_upcoming(item, run_date, timezone_name),
        lambda item: _clean_text(item.get("impact")) in {"High", "Medium"} and has_forecast_or_is_policy(item),
        lambda item: has_forecast_or_is_policy(item),
    ]

    selected: list[CalendarEvent] = []
    seen: set[tuple[str, str, str]] = set()
    for group_index, group in enumerate(groups):
        candidates = [item for item in raw_events if isinstance(item, dict) and group(item)]
        for raw_event in sorted(candidates, key=lambda item: _event_sort_key(item, run_date, timezone_name)):
            event = _raw_event_to_calendar_event(raw_event, timezone_name)
            if event is None or _event_identity(event) in seen:
                continue
            selected.append(event)
            seen.add(_event_identity(event))
            if len(selected) >= max_events:
                return selected
        if group_index == 1 and len(selected) >= minimum_upcoming_events:
            return selected
    return selected


def _is_upcoming(raw_event: dict, run_date: date, timezone_name: str) -> bool:
    local_time = _parse_event_datetime(raw_event.get("date")).astimezone(ZoneInfo(timezone_name))
    return local_time.date() >= run_date


def _normalize_payload(payload: object) -> list[dict]:
    if not isinstance(payload, list):
        raise ValueError("calendar payload was not a list")
    return [item for item in payload if isinstance(item, dict)]


def _read_calendar_cache(cache_path: Path) -> list[dict] | None:
    if not cache_path.exists():
        return None
    return _normalize_payload(json.loads(cache_path.read_text(encoding="utf-8")))


def _write_calendar_cache(cache_path: Path, payload: object) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload), encoding="utf-8")


def fetch_faireconomy_calendar(client: httpx.Client, cache_path: Path = CALENDAR_CACHE_PATH) -> CalendarFetchResult:
    try:
        response = client.get(FAIRECONOMY_WEEKLY_URL)
        response.raise_for_status()
        payload = response.json()
        raw_events = _normalize_payload(payload)
        _write_calendar_cache(cache_path, payload)
        return CalendarFetchResult(raw_events=raw_events, source=FAIRECONOMY_SOURCE)
    except Exception as exc:  # noqa: BLE001 - cache fallback is intentional here.
        cached_events = _read_calendar_cache(cache_path)
        if cached_events is None:
            raise
        return CalendarFetchResult(
            raw_events=cached_events,
            source=f"{FAIRECONOMY_SOURCE}:cache",
            refresh_error=str(exc),
        )


def replace_calendar_with_live(
    data: BriefData,
    *,
    run_date: date,
    timezone_name: str,
    cache_path: Path = CALENDAR_CACHE_PATH,
    client_factory: Callable[[], httpx.Client] | None = None,
) -> CalendarDataResult:
    client_factory = client_factory or (
        lambda: httpx.Client(
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (compatible; macro-news-agent/0.1)"},
            follow_redirects=True,
        )
    )

    errors: dict[str, str] = {}
    sources: list[str] = []
    fallback_events = [event.event for event in data.calendar]

    try:
        ZoneInfo(timezone_name)
        with client_factory() as client:
            fetch_result = fetch_faireconomy_calendar(client, cache_path=cache_path)
        calendar = _select_events(fetch_result.raw_events, run_date=run_date, timezone_name=timezone_name)
        if not calendar:
            raise ValueError("calendar source returned no usable events")
        if fetch_result.refresh_error:
            errors["calendar_live_refresh"] = fetch_result.refresh_error
    except Exception as exc:  # noqa: BLE001 - logged fallback is intentional here.
        errors["calendar"] = str(exc)
        return CalendarDataResult(
            data=data,
            live_events=[],
            fallback_events=fallback_events,
            errors=errors,
            sources=[],
        )

    sources.append(fetch_result.source)
    updated = replace(
        data,
        calendar=calendar,
        assumptions=[
            *data.assumptions,
            "Calendar uses the live Forex Factory/Fair Economy weekly feed when available and sample fallback rows when it fails.",
        ],
        data_sources=[*data.data_sources, *sources],
    )
    return CalendarDataResult(
        data=updated,
        live_events=[event.event for event in calendar],
        fallback_events=[],
        errors=errors,
        sources=sources,
    )
