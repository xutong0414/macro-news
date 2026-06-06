from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta
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
    YahooSpec("Gold", "GC=F", "$", 2, "pct", "yahoo_chart:GC=F", "Gold tests whether real-rate pressure is biting."),
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


def quote_to_row(quote: LiveQuote) -> MarketRow:
    return MarketRow(
        asset=quote.asset,
        close=_format_value(quote.close, quote.unit, quote.decimals),
        prior=_format_value(quote.prior, quote.unit, quote.decimals),
        change=_format_change(quote.close, quote.prior, quote.change_style),
        so_what=quote.so_what,
    )


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
    closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
    valid_closes = [value for value in (_safe_float(item) for item in closes) if value is not None]
    if len(valid_closes) < 2:
        raise ValueError("not enough close values")
    return LiveQuote(
        asset=spec.asset,
        close=valid_closes[-1],
        prior=valid_closes[-2],
        unit=spec.unit,
        decimals=spec.decimals,
        change_style=spec.change_style,
        source=spec.source,
        so_what=spec.so_what,
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
) -> LiveQuote:
    start = run_date - timedelta(days=7)
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
        series=tuple((day[-5:], value) for day, value in dated_values[-5:]) if include_series else (),
    )


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
    target_order = ["S&P 500", "Euro Stoxx 50", "US 10Y yield", "Germany 10Y yield", "DXY", "EUR/USD", "USD/JPY", "Gold", "WTI oil", "BTC"]
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
                    live_rows[asset] = quote_to_row(cached_quote)
                    cached_assets.append(asset)
                    sources.append(f"{cached_quote.source}:cache")
                    if cached_quote.asset == "USD/JPY" and cached_quote.series:
                        live_chart_series = list(cached_quote.series)
                    errors[asset] = str(exc)
                elif asset in fallback_by_asset:
                    fallback_assets.append(asset)
                    errors[asset] = str(exc)
                continue
            live_rows[asset] = quote_to_row(quote)
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
            merged_rows.append(fallback_by_asset[asset])

    for row in data.market_rows:
        if row.asset not in target_order:
            merged_rows.append(row)

    total_assets = len(merged_rows)
    if fallback_assets or cached_assets:
        status_parts = [f"live public sources refreshed {len(live_assets)}/{total_assets} dashboard rows"]
        if cached_assets:
            status_parts.append(f"cached real-source rows used for {', '.join(cached_assets)}")
        if fallback_assets:
            status_parts.append(f"scaffold fallback used for {', '.join(fallback_assets)}")
        else:
            status_parts.append("no scaffold fallback rows used")
        market_note = f"Market: {'; '.join(status_parts)}."
    else:
        market_note = f"Market: all {total_assets} dashboard rows refreshed from live public sources."

    assumptions = [
        *data.assumptions,
        "Market dashboard uses public live sources where available, cached real-source rows for temporary outages, and scaffold fallback only when neither is available.",
    ]
    try:
        zone = ZoneInfo(timezone_name)
    except Exception:  # noqa: BLE001 - timezone validation happens in config.
        zone = ZoneInfo("Asia/Hong_Kong")
    reference_now = reference_now or datetime.now(zone)
    extracted_at = reference_now.astimezone(zone).strftime("%Y-%m-%d %H:%M %Z")
    dashboard_notes = [
        "Dashboard scope: equities (S&P 500, Euro Stoxx 50), rates (US/Germany 10Y), FX (DXY, EUR/USD, USD/JPY), gold, oil, and BTC.",
        (
            f"Timing basis: extracted at {extracted_at}; equity/rate/commodity rows use latest source daily close vs prior source daily close; "
            "FX rows use latest available Frankfurter reference fixing vs prior fixing; BTC uses query-time price vs rolling 24-hour change."
        ),
        "Hong Kong morning caveat: around 07:00-08:00 HKT, US/EU cash markets are closed from prior sessions, while FX and BTC are continuous and Asia may already be open.",
        "Sources: Yahoo Finance chart endpoint for equities/rates/DXY/gold/oil, Frankfurter for EUR/USD and USD/JPY, CoinGecko for BTC; Source Status shows live, cached, or scaffold fallback rows.",
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
