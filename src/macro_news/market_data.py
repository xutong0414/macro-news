from __future__ import annotations

import csv
import io
import json
import math
import re
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import httpx

from .sample_data import BriefData, MarketRow

MARKET_CACHE_PATH = Path(".cache") / "market" / "live_quotes.json"


@dataclass(frozen=True)
class LiveQuote:
    asset: str
    close: float
    prior: float
    unit: str
    decimals: int
    change_style: str
    source: str
    so_what: str
    as_of: str
    series: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class MarketDataResult:
    data: BriefData
    live_assets: list[str]
    cached_assets: list[str]
    fallback_assets: list[str]
    errors: dict[str, str]
    sources: list[str]


@dataclass(frozen=True)
class YahooSpec:
    asset: str
    symbol: str
    unit: str
    decimals: int
    change_style: str
    source: str
    so_what: str


YAHOO_SPECS = [
    YahooSpec("S&P 500", "^GSPC", "", 2, "pct", "yahoo_chart:^GSPC", "US equity risk tone frames the global open."),
    YahooSpec("Euro Stoxx 50", "^STOXX50E", "", 2, "pct", "yahoo_chart:^STOXX50E", "European equities show whether risk appetite is broadening."),
    YahooSpec("US 10Y yield", "^TNX", "%", 2, "bp", "yahoo_chart:^TNX", "Treasury duration pressure drives USD/JPY, gold, and EM debt."),
    YahooSpec("DXY", "DX-Y.NYB", "", 2, "pct", "yahoo_chart:DX-Y.NYB", "Dollar direction is central for the assumed FX and EM book."),
    YahooSpec("Gold", "GC=F", "$", 2, "pct", "yahoo_chart:GC=F", "Gold tests whether rate or dollar pressure is biting."),
    YahooSpec("WTI oil", "CL=F", "$", 2, "pct", "yahoo_chart:CL=F", "Oil matters for inflation risk and rates pricing."),
]


def _format_value(value: float, unit: str, decimals: int) -> str:
    formatted = f"{value:,.{decimals}f}"
    if unit == "$":
        return f"${formatted}"
    if unit == "%":
        return f"{formatted}%"
    return formatted


def _format_change(close: float, prior: float, style: str) -> str:
    if prior == 0:
        return "n/a"
    if style == "bp":
        change = (close - prior) * 100
        return f"{change:+.0f} bp"
    pct = (close / prior - 1) * 100
    return f"{pct:+.1f}%"


def _safe_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _move_direction(quote: LiveQuote) -> str:
    if quote.prior == 0:
        return "flat"
    if quote.change_style == "bp":
        change = (quote.close - quote.prior) * 100
        if change > 1:
            return "up"
        if change < -1:
            return "down"
        return "flat"
    pct_change = (quote.close / quote.prior - 1) * 100
    if pct_change > 0.2:
        return "up"
    if pct_change < -0.2:
        return "down"
    return "flat"


def _why_it_matters(quote: LiveQuote) -> str:
    direction = _move_direction(quote)
    asset = quote.asset
    if asset == "S&P 500":
        return {
            "up": "Risk tone improved; EM beta has some support if rates and the dollar stay contained.",
            "down": "Risk tone softened; EM debt and high-beta FX should trade defensively.",
            "flat": "US equities give little direction; rates and FX are the cleaner overnight signal.",
        }[direction]
    if asset == "Euro Stoxx 50":
        return {
            "up": "Eurozone risk appetite is firming, a useful cross-check against the US equity signal.",
            "down": "European risk appetite is fading, so the equity weakness is not just a US story.",
            "flat": "Europe adds little new risk signal; watch rates and EUR/USD for the cleaner read.",
        }[direction]
    if asset == "US 10Y yield":
        return {
            "up": "Higher Treasury yields pressure gold and EM duration, while keeping dollar carry supported.",
            "down": "Lower Treasury yields ease pressure on gold and EM duration, and can soften dollar carry.",
            "flat": "Treasuries are not moving the story; watch dollar and commodity signals instead.",
        }[direction]
    if asset == "DXY":
        return {
            "up": "Dollar strength tightens EM financing conditions and is a headwind for gold and commodities.",
            "down": "A softer dollar eases EM financing pressure and gives gold more room to stabilize.",
            "flat": "The dollar is not adding a fresh shock; pair-specific FX moves matter more today.",
        }[direction]
    if asset == "EUR/USD":
        return {
            "up": "Euro firmness trims broad-dollar pressure; confirm with DXY before adding USD exposure.",
            "down": "Euro weakness confirms dollar pressure and keeps policy-divergence trades in focus.",
            "flat": "EUR/USD is not driving the dollar story; look to DXY and USD/JPY for signal.",
        }[direction]
    if asset == "USD/JPY":
        return {
            "up": "The long is working, but extension raises intervention and crowded-position risk.",
            "down": "Yen strength tests the long and would make intervention headlines more credible.",
            "flat": "Spot is pausing near elevated levels; intervention risk matters more than the tick change.",
        }[direction]
    if asset == "Gold":
        return {
            "up": "Gold is resisting rates and dollar pressure, giving the overweight some cushion.",
            "down": "Gold weakness shows rate or dollar pressure is biting the overweight.",
            "flat": "Gold is holding steady; rates and DXY will decide whether the overweight has cover.",
        }[direction]
    if asset == "WTI oil":
        return {
            "up": "Oil strength adds inflation risk and can delay the easing impulse rates want to price.",
            "down": "Lower oil eases inflation pressure and gives duration-sensitive assets some relief.",
            "flat": "Oil is not changing the inflation story today; rates carry the cleaner signal.",
        }[direction]
    if asset == "BTC":
        return {
            "up": "Speculative risk appetite is firm, but this remains a cross-check rather than a core book driver.",
            "down": "Speculative risk appetite is softer, reinforcing caution toward high-beta exposures.",
            "flat": "Crypto is not adding a risk signal; treat it as background, not a portfolio driver.",
        }[direction]
    if asset == "Japan 10Y yield":
        return {
            "up": "Higher JGB yields put Japan-rate pressure on the long USD/JPY view; compare against the US yield move.",
            "down": "Lower JGB yields reduce Japan-rate pressure on the long USD/JPY view.",
            "flat": "Japan rates add little today; intervention risk is the cleaner USD/JPY watchpoint.",
        }[direction]
    return quote.so_what


def _status_for_quote(quote: LiveQuote, run_date: date, *, cached: bool = False) -> str:
    if cached:
        return "†"
    as_of_date = quote.as_of[:10]
    if as_of_date and as_of_date != run_date.isoformat():
        return "*"
    return "Live"


def quote_to_row(quote: LiveQuote, run_date: date, *, cached: bool = False) -> MarketRow:
    as_of = quote.as_of or ("cached date unknown" if cached else "")
    return MarketRow(
        asset=quote.asset,
        close=_format_value(quote.close, quote.unit, quote.decimals),
        prior=_format_value(quote.prior, quote.unit, quote.decimals),
        change=_format_change(quote.close, quote.prior, quote.change_style),
        so_what=_why_it_matters(quote),
        as_of=as_of,
        status=_status_for_quote(quote, run_date, cached=cached),
    )


def blank_market_row(asset: str) -> MarketRow:
    return MarketRow(asset=asset, close="", prior="", change="", so_what="", as_of="", status="")


def fetch_yahoo_chart(client: httpx.Client, spec: YahooSpec) -> LiveQuote:
    response = None
    last_error: Exception | None = None
    for host in ("query2.finance.yahoo.com", "query1.finance.yahoo.com"):
        try:
            response = client.get(
                f"https://{host}/v8/finance/chart/{spec.symbol}",
                params={"range": "5d", "interval": "1d"},
            )
            response.raise_for_status()
            break
        except Exception as exc:  # noqa: BLE001 - alternate Yahoo host is intentional.
            last_error = exc
            response = None
    if response is None:
        raise RuntimeError(f"Yahoo chart request failed: {last_error}") from last_error
    payload = response.json()
    result = payload.get("chart", {}).get("result", [])
    if not result:
        raise ValueError("missing chart result")
    timestamps = result[0].get("timestamp", [])
    closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
    dated_closes = [
        (int(timestamp), value)
        for timestamp, value in zip(timestamps, (_safe_float(item) for item in closes), strict=False)
        if value is not None
    ]
    if len(dated_closes) < 2:
        raise ValueError("not enough close values")
    as_of = datetime.fromtimestamp(dated_closes[-1][0], timezone.utc).date().isoformat()
    return LiveQuote(
        asset=spec.asset,
        close=dated_closes[-1][1],
        prior=dated_closes[-2][1],
        unit=spec.unit,
        decimals=spec.decimals,
        change_style=spec.change_style,
        source=spec.source,
        so_what=spec.so_what,
        as_of=as_of,
    )


def _read_market_cache(cache_path: Path) -> dict[str, LiveQuote]:
    if not cache_path.exists():
        return {}
    try:
        raw_cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw_cache, dict):
        return {}
    quotes: dict[str, LiveQuote] = {}
    for asset, item in raw_cache.items():
        if not isinstance(item, dict):
            continue
        try:
            quotes[asset] = LiveQuote(
                asset=str(item["asset"]),
                close=float(item["close"]),
                prior=float(item["prior"]),
                unit=str(item["unit"]),
                decimals=int(item["decimals"]),
                change_style=str(item["change_style"]),
                source=str(item["source"]),
                so_what=str(item["so_what"]),
                as_of=str(item.get("as_of", "")),
                series=tuple((str(label), float(value)) for label, value in item.get("series", [])),
            )
        except (KeyError, TypeError, ValueError):
            continue
    return quotes


def _write_market_cache(cache_path: Path, quotes: dict[str, LiveQuote]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({asset: asdict(quote) for asset, quote in quotes.items()}, indent=2),
        encoding="utf-8",
    )


def fetch_fx_reference(
    client: httpx.Client,
    *,
    run_date: date,
    asset: str,
    base_currency: str,
    quote_currency: str,
    decimals: int,
    source: str,
    so_what: str,
    include_series: bool = False,
    history_days: int = 7,
) -> LiveQuote:
    start = run_date - timedelta(days=history_days)
    response = client.get(
        f"https://api.frankfurter.app/{start.isoformat()}..{run_date.isoformat()}",
        params={"from": base_currency, "to": quote_currency},
    )
    response.raise_for_status()
    rates = response.json().get("rates", {})
    dated_values = [
        (_day, _safe_float(item.get(quote_currency)))
        for _day, item in sorted(rates.items())
        if isinstance(item, dict)
    ]
    dated_values = [(day, value) for day, value in dated_values if value is not None]
    values = [value for _day, value in dated_values]
    if len(values) < 2:
        raise ValueError(f"not enough {asset} values")
    return LiveQuote(
        asset=asset,
        close=values[-1],
        prior=values[-2],
        unit="",
        decimals=decimals,
        change_style="pct",
        source=source,
        so_what=so_what,
        as_of=dated_values[-1][0],
        series=tuple((day, value) for day, value in dated_values) if include_series else (),
    )


def _parse_japan_mof_date(value: str) -> str:
    text = value.strip()
    match = re.match(r"R(\d+)\.(\d+)\.(\d+)", text, flags=re.IGNORECASE)
    if not match:
        return text
    year = 2018 + int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    return date(year, month, day).isoformat()


def fetch_eurusd(client: httpx.Client, run_date: date) -> LiveQuote:
    return fetch_fx_reference(
        client,
        run_date=run_date,
        asset="EUR/USD",
        base_currency="EUR",
        quote_currency="USD",
        decimals=4,
        source="frankfurter:EURUSD",
        so_what="The largest FX pair is the cleanest euro-dollar policy divergence read.",
    )


def fetch_usdjpy(client: httpx.Client, run_date: date) -> LiveQuote:
    return fetch_fx_reference(
        client,
        run_date=run_date,
        asset="USD/JPY",
        base_currency="USD",
        quote_currency="JPY",
        decimals=2,
        source="frankfurter:USDJPY",
        so_what="Yen direction is the direct read-through for the assumed long USD/JPY.",
        include_series=True,
        history_days=92,
    )


def fetch_japan_10y_mof(client: httpx.Client) -> LiveQuote:
    response = client.get("https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv")
    response.raise_for_status()
    text = response.content.decode("cp932")
    rows = csv.reader(io.StringIO(text))
    dated_values: list[tuple[str, float]] = []
    for row in rows:
        if len(row) <= 10:
            continue
        value = _safe_float(row[10])
        if value is not None:
            dated_values.append((_parse_japan_mof_date(row[0]), value))
    if len(dated_values) < 2:
        raise ValueError("not enough Japan 10Y yield values")
    return LiveQuote(
        asset="Japan 10Y yield",
        close=dated_values[-1][1],
        prior=dated_values[-2][1],
        unit="%",
        decimals=3,
        change_style="bp",
        source="mof_japan:jgbcm_10y",
        so_what="Japan rates are a direct risk factor for the assumed long USD/JPY.",
        as_of=dated_values[-1][0],
    )


def fetch_btc(client: httpx.Client) -> LiveQuote:
    response = client.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": "bitcoin", "vs_currencies": "usd", "include_24hr_change": "true"},
    )
    response.raise_for_status()
    bitcoin = response.json().get("bitcoin", {})
    close = _safe_float(bitcoin.get("usd"))
    change = _safe_float(bitcoin.get("usd_24h_change"))
    if close is None or change is None:
        raise ValueError("missing BTC price or 24h change")
    prior = close / (1 + change / 100)
    return LiveQuote(
        asset="BTC",
        close=close,
        prior=prior,
        unit="$",
        decimals=0,
        change_style="pct",
        source="coingecko:bitcoin",
        so_what="Crypto risk appetite is a useful cross-check, not core to the assumed book.",
        as_of=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )


def replace_market_rows_with_live(
    data: BriefData,
    *,
    run_date: date,
    timezone_name: str = "Asia/Hong_Kong",
    reference_now: datetime | None = None,
    cache_path: Path = MARKET_CACHE_PATH,
    client_factory: Callable[[], httpx.Client] | None = None,
) -> MarketDataResult:
    client_factory = client_factory or (
        lambda: httpx.Client(
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (compatible; macro-news-agent/0.1)"},
            follow_redirects=True,
        )
    )

    fallback_by_asset = {row.asset: row for row in data.market_rows}
    target_order = [
        "S&P 500",
        "Euro Stoxx 50",
        "US 10Y yield",
        "Japan 10Y yield",
        "DXY",
        "EUR/USD",
        "USD/JPY",
        "Gold",
        "WTI oil",
        "BTC",
    ]
    cached_quotes = _read_market_cache(cache_path)
    cache_updates = dict(cached_quotes)
    live_rows: dict[str, MarketRow] = {}
    live_chart_series: list[tuple[str, float]] | None = None
    live_assets: list[str] = []
    cached_assets: list[str] = []
    fallback_assets: list[str] = []
    errors: dict[str, str] = {}
    sources: list[str] = []

    with client_factory() as client:
        fetchers: list[tuple[str, Callable[[], LiveQuote]]] = [
            *[(spec.asset, lambda spec=spec: fetch_yahoo_chart(client, spec)) for spec in YAHOO_SPECS],
            ("Japan 10Y yield", lambda: fetch_japan_10y_mof(client)),
            ("EUR/USD", lambda: fetch_eurusd(client, run_date)),
            ("USD/JPY", lambda: fetch_usdjpy(client, run_date)),
            ("BTC", lambda: fetch_btc(client)),
        ]

        for asset, fetcher in fetchers:
            try:
                quote = fetcher()
            except Exception as exc:  # noqa: BLE001 - logged fallback is intentional here.
                cached_quote = cached_quotes.get(asset)
                if cached_quote is not None:
                    live_rows[asset] = quote_to_row(cached_quote, run_date, cached=True)
                    cached_assets.append(asset)
                    sources.append(f"{cached_quote.source}:cache")
                    if cached_quote.asset == "USD/JPY" and cached_quote.series:
                        live_chart_series = list(cached_quote.series)
                    errors[asset] = str(exc)
                elif asset in fallback_by_asset:
                    fallback_assets.append(asset)
                    errors[asset] = str(exc)
                continue
            live_rows[asset] = quote_to_row(quote, run_date)
            live_assets.append(asset)
            sources.append(quote.source)
            cache_updates[asset] = quote
            if quote.asset == "USD/JPY" and quote.series:
                live_chart_series = list(quote.series)

    if live_assets:
        _write_market_cache(cache_path, cache_updates)

    merged_rows: list[MarketRow] = []
    for asset in target_order:
        if asset in live_rows:
            merged_rows.append(live_rows[asset])
        elif asset in fallback_by_asset:
            if asset not in fallback_assets:
                fallback_assets.append(asset)
            merged_rows.append(blank_market_row(asset))

    for row in data.market_rows:
        if row.asset not in target_order:
            merged_rows.append(row)

    total_assets = len(merged_rows)
    source_links = (
        "[Yahoo Finance](https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC), "
        "[Japan MOF](https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv), "
        "[Frankfurter](https://frankfurter.dev/), and "
        "[CoinGecko](https://www.coingecko.com/en/api)"
    )
    if fallback_assets or cached_assets:
        status_parts = [f"{source_links}; live public sources refreshed {len(live_assets)}/{total_assets} dashboard rows"]
        if cached_assets:
            status_parts.append(f"cached real-source rows used for {', '.join(cached_assets)}")
        if fallback_assets:
            status_parts.append(f"no live/cached real row for {', '.join(fallback_assets)}; cells left blank")
        else:
            status_parts.append("no scaffold fallback rows used")
        market_note = f"Market: {'; '.join(status_parts)}."
    else:
        market_note = f"Market: {source_links}; all {total_assets} dashboard rows refreshed from live public sources."

    assumptions = [
        *data.assumptions,
        "Market dashboard uses public live sources where available, cached real-source rows for temporary outages, and blank cells rather than scaffold values when neither is available.",
    ]
    try:
        zone = ZoneInfo(timezone_name)
    except Exception:  # noqa: BLE001 - timezone validation happens in config.
        zone = ZoneInfo("Asia/Hong_Kong")
    reference_now = reference_now or datetime.now(zone)
    extracted_at = reference_now.astimezone(zone).strftime("%Y-%m-%d %H:%M %Z")
    dashboard_notes = [
        "Dashboard scope: equities (S&P 500, Euro Stoxx 50), rates (US/Japan 10Y), FX (DXY, EUR/USD, USD/JPY), gold, oil, and BTC.",
        (
            f"Timing basis: extracted at {extracted_at}; equity/rate/commodity rows use latest source daily close vs prior source daily close; "
            "Frankfurter FX rows use the latest published daily reference rate vs the immediately previous published daily reference rate; "
            "BTC uses query-time price vs rolling 24-hour change."
        ),
        "Additional information about timing: around 07:00-08:00 HKT, US/EU cash markets are closed from prior sessions, while FX and BTC are continuous and Asia may already be open.",
        "Status marker basis: asset labels show * when the live source's latest valid date is older than the run date, usually because of weekend, holiday, or publication lag; asset labels show † when cached real-source data was used after a live refresh failed. Rows without a marker refreshed for the run date or query time. If no live or cached real row exists, value cells are left blank rather than filled with scaffold/sample numbers.",
        (
            "Sources: [Yahoo Finance chart endpoint](https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC) for equities/US rates/DXY/gold/oil, "
            "[Japan MOF JGB yield CSV](https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv) for Japan 10Y, "
            "[Frankfurter](https://frankfurter.dev/) for EUR/USD and USD/JPY, "
            "[CoinGecko](https://www.coingecko.com/en/api) for BTC."
        ),
    ]
    updated = replace(
        data,
        market_rows=merged_rows,
        chart_series=live_chart_series or data.chart_series,
        assumptions=assumptions,
        data_sources=[*data.data_sources, *sources],
        source_notes=[*[note for note in data.source_notes if not note.startswith("Market:")], market_note],
        dashboard_notes=dashboard_notes,
    )
    return MarketDataResult(
        data=updated,
        live_assets=live_assets,
        cached_assets=cached_assets,
        fallback_assets=fallback_assets,
        errors=errors,
        sources=sources,
    )
