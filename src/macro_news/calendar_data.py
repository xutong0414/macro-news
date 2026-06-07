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

REQUIRED_SESSIONS = ("Asia", "Europe", "US")


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


def _has_forecast(raw_event: dict) -> bool:
    return bool(_clean_text(raw_event.get("forecast")))


def _is_policy_event(raw_event: dict) -> bool:
    title = _clean_text(raw_event.get("title")).lower()
    return any(word in title for word in ("speaks", "speech", "fed", "fomc", "ecb", "boe", "boj", "rba", "rate decision"))


def _is_usable_event(raw_event: dict) -> bool:
    if not isinstance(raw_event, dict):
        return False
    impact = _clean_text(raw_event.get("impact"))
    if impact not in IMPACT_SCORE:
        return False
    return _has_forecast(raw_event) or _is_policy_event(raw_event) or impact in {"High", "Medium"}


def _session_for_event(raw_event: dict) -> str:
    return _session_for_currency(_clean_text(raw_event.get("country")).upper())


def _event_identity(event: CalendarEvent) -> tuple[str, str, str]:
    return (event.session, event.time, event.event)


def _format_event_time(local_time: datetime, run_date: date, reference_now: datetime | None = None) -> str:
    days_from_run = (local_time.date() - run_date).days
    clock = local_time.strftime("%H:%M")
    zone = local_time.strftime("%Z") or "local"
    if days_from_run == 0:
        if reference_now is not None and local_time < reference_now:
            return f"Earlier today {clock} {zone}"
        return f"Today {clock} {zone}"
    if days_from_run == 1:
        return f"Tomorrow {clock} {zone}"
    return f"{local_time.strftime('%a %b %d')} {clock} {zone}"


def _calendar_status(local_time: datetime, run_date: date, *, cached: bool) -> str:
    if cached:
        return "†"
    if local_time.date() != run_date:
        return "*"
    return "Live"


def _raw_event_to_calendar_event(
    raw_event: dict,
    timezone_name: str,
    run_date: date,
    reference_now: datetime | None = None,
    cached: bool = False,
) -> CalendarEvent | None:
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
        time=_format_event_time(local_time, run_date, reference_now),
        event=f"{currency} {title}",
        consensus=forecast or "n/a",
        why_it_matters=_why_it_matters(title, currency, impact),
        event_date=local_time.date().isoformat(),
        status=_calendar_status(local_time, run_date, cached=cached),
    )


def _event_sort_key(
    raw_event: dict,
    run_date: date,
    timezone_name: str,
    reference_now: datetime | None = None,
) -> tuple[int, int, int, datetime]:
    local_time = _parse_event_datetime(raw_event.get("date")).astimezone(ZoneInfo(timezone_name))
    days_from_run = (local_time.date() - run_date).days
    is_future = local_time >= reference_now if reference_now is not None else days_from_run >= 0
    future_penalty = 0 if is_future else 1
    impact = _clean_text(raw_event.get("impact"))
    forecast_or_policy_penalty = 0 if _has_forecast(raw_event) or _is_policy_event(raw_event) else 1
    return (future_penalty, forecast_or_policy_penalty, abs(days_from_run), -IMPACT_SCORE.get(impact, 0), local_time)


def _select_events(
    raw_events: list[dict],
    *,
    run_date: date,
    timezone_name: str,
    reference_now: datetime | None = None,
    max_events: int = 4,
    cached: bool = False,
) -> list[CalendarEvent]:
    usable_events = [item for item in raw_events if _is_usable_event(item)]
    selected: list[CalendarEvent] = []
    seen: set[tuple[str, str, str]] = set()

    def add_event(raw_event: dict) -> bool:
        event = _raw_event_to_calendar_event(raw_event, timezone_name, run_date, reference_now, cached=cached)
        if event is None or _event_identity(event) in seen:
            return False
        selected.append(event)
        seen.add(_event_identity(event))
        return len(selected) >= max_events

    for session in REQUIRED_SESSIONS:
        candidates = [item for item in usable_events if _session_for_event(item) == session]
        for raw_event in sorted(candidates, key=lambda item: _event_sort_key(item, run_date, timezone_name, reference_now)):
            if add_event(raw_event):
                return selected
            break

    for raw_event in sorted(usable_events, key=lambda item: _event_sort_key(item, run_date, timezone_name, reference_now)):
        if add_event(raw_event):
            return selected
    return selected


def _is_upcoming(
    raw_event: dict,
    run_date: date,
    timezone_name: str,
    reference_now: datetime | None = None,
) -> bool:
    local_time = _parse_event_datetime(raw_event.get("date")).astimezone(ZoneInfo(timezone_name))
    if reference_now is not None:
        return local_time >= reference_now
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
    reference_now: datetime | None = None,
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
        zone = ZoneInfo(timezone_name)
        if reference_now is None and run_date == datetime.now(zone).date():
            reference_now = datetime.now(zone)
        with client_factory() as client:
            fetch_result = fetch_faireconomy_calendar(client, cache_path=cache_path)
        source_is_cached = fetch_result.source.endswith(":cache")
        calendar = _select_events(
            fetch_result.raw_events,
            run_date=run_date,
            timezone_name=timezone_name,
            reference_now=reference_now,
            cached=source_is_cached,
        )
        if not calendar:
            raise ValueError("calendar source returned no usable events")
        if fetch_result.refresh_error:
            errors["calendar_live_refresh"] = fetch_result.refresh_error
    except Exception as exc:  # noqa: BLE001 - logged fallback is intentional here.
        errors["calendar"] = str(exc)
        fallback_note = "Calendar: no verified live or cached calendar rows available; calendar table left blank rather than using scaffold events."
        fallback_data = replace(
            data,
            calendar=[],
            source_notes=[*[note for note in data.source_notes if not note.startswith("Calendar:")], fallback_note],
        )
        return CalendarDataResult(
            data=fallback_data,
            live_events=[],
            fallback_events=[],
            errors=errors,
            sources=[],
        )

    sources.append(fetch_result.source)
    if fetch_result.refresh_error:
        calendar_note = "Calendar: cached Fair Economy weekly feed used after live refresh failed; selector still targets Asia/Europe/US coverage when available."
    else:
        calendar_note = "Calendar: live Fair Economy weekly feed used; selector targets Asia/Europe/US coverage and labels same-day, next-session, or nearest source-week events."
    updated = replace(
        data,
        calendar=calendar,
        assumptions=[
            *data.assumptions,
            "Calendar uses the live Forex Factory/Fair Economy weekly feed when available, cached real rows after rate limits, and blank output rather than scaffold rows if no verified calendar data exists.",
            "Calendar live mode leaves the table blank instead of using scaffold events when neither live nor cached real calendar rows are available.",
        ],
        data_sources=[*data.data_sources, *sources],
        source_notes=[*[note for note in data.source_notes if not note.startswith("Calendar:")], calendar_note],
    )
    return CalendarDataResult(
        data=updated,
        live_events=[event.event for event in calendar],
        fallback_events=[],
        errors=errors,
        sources=sources,
    )
