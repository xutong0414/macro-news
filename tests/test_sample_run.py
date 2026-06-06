from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from macro_news.config import Settings, normalize_timezone
from macro_news.costing import TokenUsage
from macro_news.llm import SynthesisResult, parse_narrative_response
from macro_news.market_data import replace_market_rows_with_live
from macro_news.render import render_markdown
import macro_news.runner as runner_module
from macro_news.calendar_data import replace_calendar_with_live
from macro_news.runner import run_brief
from macro_news.sample_data import build_sample_brief_data
from macro_news.theme_data import ThemeSource, replace_theme_radar_with_live


def _word_count(text: str) -> int:
    return len(text.split())


def _calendar_reference_now() -> datetime:
    return datetime(2026, 6, 6, 0, 0, tzinfo=ZoneInfo("Asia/Hong_Kong"))


def test_timezone_aliases_normalize() -> None:
    assert normalize_timezone("Hong Kong") == "Asia/Hong_Kong"
    assert normalize_timezone("HongKong") == "Asia/Hong_Kong"
    assert normalize_timezone("Asia/Hong Kong") == "Asia/Hong_Kong"
    assert normalize_timezone("Asia/Shanghai") == "Asia/Shanghai"


def test_sample_brief_contains_required_sections() -> None:
    brief = render_markdown(build_sample_brief_data())
    required = [
        "Overnight Market Dashboard",
        "The 3 Things That Matter Today",
        "Today's Calendar",
        "One Chart Worth Seeing",
        "Theme Radar",
        "Contrarian Corner",
    ]
    for section in required:
        assert section in brief


def test_sample_brief_assignment_word_limits() -> None:
    data = build_sample_brief_data()

    assert all(_word_count(item) <= 80 for item in data.three_things)
    assert _word_count(data.chart_caption) <= 30
    assert all(60 <= _word_count(item.summary) <= 100 for item in data.theme_radar)
    assert 50 <= _word_count(data.contrarian_corner) <= 100


def test_parse_narrative_response_replaces_narrative_sections() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "Rates remain the cleanest overnight signal as higher yields reinforce dollar momentum. So what: keep USD/JPY as the main expression, but watch whether gold starts reacting more negatively to real-rate pressure.",
        "Oil strength adds an awkward inflation tail to an otherwise calm risk tape. So what: EM duration exposure should stay hedged until energy stops pushing against the easing narrative.",
        "Equities look firm, but the cross-asset mix is more about rates and the dollar than broad reflation. So what: avoid reading this as a simple risk-on day for the whole book."
      ],
      "theme_radar": [
        {
          "title": "The term premium refuses to disappear",
          "source": "Sample macro research note",
          "link": "https://example.com/research/term-premium",
          "summary": "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. The point is not that growth is suddenly stronger, but that investors want more compensation for duration risk when supply headlines keep returning. The note says positioning remains too relaxed.",
          "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring."
        }
      ],
      "contrarian_corner": "The market may be too relaxed about the idea that policy easing can arrive without a renewed inflation problem. If oil, freight, or shelter data firm while Treasury supply keeps term premium elevated, the next surprise is higher real rates rather than weaker growth. That would support the dollar and challenge duration-heavy trades."
    }
    """

    generated = parse_narrative_response(response, base)

    assert generated.market_rows == base.market_rows
    assert generated.calendar == base.calendar
    assert generated.chart_series == base.chart_series
    assert generated.three_things[0].startswith("Rates remain")
    assert generated.theme_radar[0].summary.startswith("The author argues")
    assert generated.contrarian_corner.startswith("The market may be")
    assert "gemini_synthesis" in generated.data_sources


def test_dry_run_writes_outputs(tmp_path) -> None:
    settings = Settings(
        llm_provider="gemini",
        gemini_api_key=None,
        gemini_model="gemini-2.5-flash-lite",
        deepseek_api_key=None,
        deepseek_model="deepseek-v4-flash",
        smtp_host=None,
        smtp_port=587,
        smtp_user=None,
        smtp_password=None,
        brief_from_email=None,
        brief_to_email=None,
        timezone="Asia/Shanghai",
        run_mode="sample",
        market_data_mode="sample",
        calendar_mode="sample",
        theme_source_mode="sample",
        output_dir=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
    )

    result = run_brief(settings, send=False)

    assert result.delivery_status == "dry_run"
    assert result.output_paths["latest_markdown"].exists()
    assert result.output_paths["latest_html"].exists()
    assert result.output_paths["latest_chart"].exists()
    assert result.log_path.exists()


def test_dry_run_with_llm_writes_usage_log(tmp_path, monkeypatch) -> None:
    settings = Settings(
        llm_provider="gemini",
        gemini_api_key="test-key",
        gemini_model="gemini-2.5-flash-lite",
        deepseek_api_key=None,
        deepseek_model="deepseek-v4-flash",
        smtp_host=None,
        smtp_port=587,
        smtp_user=None,
        smtp_password=None,
        brief_from_email=None,
        brief_to_email=None,
        timezone="Asia/Shanghai",
        run_mode="sample",
        market_data_mode="sample",
        calendar_mode="sample",
        theme_source_mode="sample",
        output_dir=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
    )

    def fake_synthesize(_settings, data):
        return SynthesisResult(
            data=replace(data, three_things=["One thing. So what: test."] * 3, data_sources=[*data.data_sources, "gemini_synthesis"]),
            token_usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, provider="gemini"),
            estimated_cost_usd=0.00003,
            provider="gemini",
            model="gemini-2.5-flash-lite",
            prompt_version="test_prompt",
        )

    monkeypatch.setattr(runner_module, "synthesize_with_gemini", fake_synthesize)

    result = run_brief(settings, send=False, use_llm=True)
    log_event = json.loads(result.log_path.read_text(encoding="utf-8"))

    assert log_event["llm_status"] == "used"
    assert log_event["token_usage"]["input_tokens"] == 100
    assert log_event["estimated_llm_cost_usd"] == 0.00003


class FakeResponse:
    def __init__(self, payload=None, text=""):
        self.payload = payload
        self.text = text

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


class FakeMarketClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url, params=None):
        params = params or {}
        if "finance/chart" in url:
            symbol = url.rsplit("/", 1)[-1]
            if symbol == "DX-Y.NYB":
                raise RuntimeError("simulated DXY outage")
            closes = {
                "^GSPC": [100.0, 102.0],
                "^STOXX50E": [200.0, 198.0],
                "^TNX": [4.40, 4.45],
                "GC=F": [2300.0, 2310.0],
                "CL=F": [80.0, 82.0],
            }[symbol]
            return FakeResponse(
                {
                    "chart": {
                        "result": [
                            {
                                "indicators": {
                                    "quote": [
                                        {
                                            "close": closes,
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            )
        if "frankfurter" in url:
            return FakeResponse({"rates": {"2026-06-04": {"JPY": 158.0}, "2026-06-05": {"JPY": 159.0}}})
        if "coingecko" in url:
            return FakeResponse({"bitcoin": {"usd": 60000, "usd_24h_change": 2.0}})
        raise AssertionError(f"Unexpected URL: {url} {params}")


def test_live_market_data_replaces_rows_and_logs_fallback() -> None:
    base = build_sample_brief_data()
    result = replace_market_rows_with_live(base, run_date=date(2026, 6, 6), client_factory=FakeMarketClient)

    row_by_asset = {row.asset: row for row in result.data.market_rows}

    assert row_by_asset["S&P 500"].close == "102.00"
    assert row_by_asset["S&P 500"].change == "+2.0%"
    assert row_by_asset["US 10Y yield"].change == "+5 bp"
    assert row_by_asset["USD/JPY"].close == "159.00"
    assert row_by_asset["BTC"].change == "+2.0%"
    assert row_by_asset["DXY"].close == "104.8"
    assert "DXY" in result.fallback_assets
    assert "DXY" in result.errors
    assert "yahoo_chart:^GSPC" in result.sources


class FakeCalendarClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url):
        assert "ff_calendar_thisweek" in url
        return FakeResponse(
            [
                {
                    "title": "Core CPI Flash Estimate y/y",
                    "country": "EUR",
                    "date": "2026-06-06T04:00:00-04:00",
                    "impact": "Medium",
                    "forecast": "2.4%",
                    "previous": "2.2%",
                },
                {
                    "title": "Non-Farm Employment Change",
                    "country": "USD",
                    "date": "2026-06-06T08:30:00-04:00",
                    "impact": "High",
                    "forecast": "85K",
                    "previous": "115K",
                },
                {
                    "title": "RatingDog Manufacturing PMI",
                    "country": "CNY",
                    "date": "2026-06-06T21:45:00-04:00",
                    "impact": "Medium",
                    "forecast": "51.4",
                    "previous": "52.2",
                },
                {
                    "title": "Bank Holiday",
                    "country": "NZD",
                    "date": "2026-06-06T16:00:00-04:00",
                    "impact": "Holiday",
                    "forecast": "",
                    "previous": "",
                },
            ]
        )


class FailingCalendarClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url):
        assert "ff_calendar_thisweek" in url
        raise RuntimeError("simulated 429")


def test_live_calendar_data_replaces_calendar_rows(tmp_path) -> None:
    base = build_sample_brief_data()
    result = replace_calendar_with_live(
        base,
        run_date=date(2026, 6, 6),
        timezone_name="Asia/Hong_Kong",
        reference_now=_calendar_reference_now(),
        cache_path=tmp_path / "calendar.json",
        client_factory=FakeCalendarClient,
    )

    event_by_name = {event.event: event for event in result.data.calendar}

    assert event_by_name["USD Non-Farm Employment Change"].session == "US"
    assert event_by_name["USD Non-Farm Employment Change"].consensus == "85K"
    assert event_by_name["EUR Core CPI Flash Estimate y/y"].session == "Europe"
    assert event_by_name["CNY RatingDog Manufacturing PMI"].session == "Asia"
    assert "NZD Bank Holiday" not in event_by_name
    assert result.fallback_events == []
    assert "faireconomy:ff_calendar_thisweek" in result.sources


def test_live_calendar_uses_cache_when_feed_refresh_fails(tmp_path) -> None:
    cache_path = tmp_path / "calendar.json"
    cache_path.write_text(
        json.dumps(
            [
                {
                    "title": "ISM Services PMI",
                    "country": "USD",
                    "date": "2026-06-06T10:00:00-04:00",
                    "impact": "High",
                    "forecast": "53.7",
                    "previous": "53.6",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = replace_calendar_with_live(
        build_sample_brief_data(),
        run_date=date(2026, 6, 6),
        timezone_name="Asia/Hong_Kong",
        reference_now=_calendar_reference_now(),
        cache_path=cache_path,
        client_factory=FailingCalendarClient,
    )

    assert result.data.calendar[0].event == "USD ISM Services PMI"
    assert result.data.calendar[0].consensus == "53.7"
    assert result.fallback_events == []
    assert "calendar_live_refresh" in result.errors
    assert result.sources == ["faireconomy:ff_calendar_thisweek:cache"]


def test_dry_run_with_live_calendar_writes_usage_log(tmp_path, monkeypatch) -> None:
    settings = Settings(
        llm_provider="gemini",
        gemini_api_key=None,
        gemini_model="gemini-2.5-flash-lite",
        deepseek_api_key=None,
        deepseek_model="deepseek-v4-flash",
        smtp_host=None,
        smtp_port=587,
        smtp_user=None,
        smtp_password=None,
        brief_from_email=None,
        brief_to_email=None,
        timezone="Asia/Hong_Kong",
        run_mode="sample",
        market_data_mode="sample",
        calendar_mode="sample",
        theme_source_mode="sample",
        output_dir=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
    )

    def fake_replace_calendar(data, *, run_date, timezone_name):
        return replace_calendar_with_live(
            data,
            run_date=run_date,
            timezone_name=timezone_name,
            reference_now=_calendar_reference_now(),
            cache_path=tmp_path / "calendar.json",
            client_factory=FakeCalendarClient,
        )

    monkeypatch.setattr(runner_module, "replace_calendar_with_live", fake_replace_calendar)

    result = run_brief(settings, send=False, run_date=date(2026, 6, 6), live_calendar=True)
    log_event = json.loads(result.log_path.read_text(encoding="utf-8"))

    assert log_event["calendar_data"]["mode"] == "live_with_fallback"
    assert "USD Non-Farm Employment Change" in log_event["calendar_data"]["live_events"]
    assert log_event["calendar_data"]["fallback_events"] == []


THEME_FEED_ONE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Why exclude food and energy from inflation measures?</title>
      <link>https://fredblog.stlouisfed.org/example/core-pce/</link>
      <pubDate>Thu, 04 Jun 2026 13:00:00 +0000</pubDate>
      <description><![CDATA[
        The Federal Reserve focuses on core PCE inflation because food and energy prices can be volatile.
        The post compares core PCE, food inflation, and energy inflation, arguing that the signal-to-noise
        ratio is better when volatile prices are excluded from the measure used for forward-looking policy.
      ]]></description>
    </item>
    <item>
      <title>Local museum attendance rises</title>
      <link>https://example.com/museum</link>
      <pubDate>Wed, 03 Jun 2026 13:00:00 +0000</pubDate>
      <description>Not relevant to macro portfolios.</description>
    </item>
  </channel>
</rss>
"""

THEME_FEED_TWO = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Why Does the U.S. Always Run a Trade Deficit?</title>
      <link>https://libertystreeteconomics.newyorkfed.org/example/trade-deficit/</link>
      <pubDate>Wed, 03 Jun 2026 11:01:00 +0000</pubDate>
      <description><![CDATA[
        The article explains the saving gap framework for the current account. It argues that the trade
        deficit is tied to the difference between domestic saving and investment, not only to tariff policy
        or bilateral trade balances. The discussion links fiscal deficits, capital inflows, and external funding.
      ]]></description>
    </item>
  </channel>
</rss>
"""


class FakeThemeClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url):
        if "source-one" in url:
            return FakeResponse(text=THEME_FEED_ONE)
        if "source-two" in url:
            return FakeResponse(text=THEME_FEED_TWO)
        raise RuntimeError("unexpected feed")


class FailingThemeClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url):
        raise RuntimeError(f"simulated feed outage: {url}")


def _theme_sources() -> list[ThemeSource]:
    return [
        ThemeSource("FRED Blog", "https://source-one.test/feed/", "theme_feed:test_fred"),
        ThemeSource("Liberty Street Economics", "https://source-two.test/feed/", "theme_feed:test_liberty"),
    ]


def test_live_theme_radar_replaces_sample_sources() -> None:
    result = replace_theme_radar_with_live(
        build_sample_brief_data(),
        client_factory=FakeThemeClient,
        sources=_theme_sources(),
    )

    titles = [item.title for item in result.data.theme_radar]

    assert "Why exclude food and energy from inflation measures?" in titles
    assert "Why Does the U.S. Always Run a Trade Deficit?" in titles
    assert result.fallback_used is False
    assert result.candidate_count == 2
    assert "theme_feed:test_fred" in result.sources
    assert "theme_feed:test_liberty" in result.sources
    assert all(60 <= _word_count(item.summary) <= 100 for item in result.data.theme_radar)
    assert all(item.link.startswith("https://") for item in result.data.theme_radar)


def test_live_theme_radar_falls_back_when_sources_fail() -> None:
    base = build_sample_brief_data()
    result = replace_theme_radar_with_live(
        base,
        client_factory=FailingThemeClient,
        sources=_theme_sources(),
    )

    assert result.data.theme_radar == base.theme_radar
    assert result.fallback_used is True
    assert result.candidate_count == 0
    assert "theme_feed:test_fred" in result.errors
    assert "theme_feed:test_liberty" in result.errors


def test_dry_run_with_live_theme_radar_writes_usage_log(tmp_path, monkeypatch) -> None:
    settings = Settings(
        llm_provider="gemini",
        gemini_api_key=None,
        gemini_model="gemini-2.5-flash-lite",
        deepseek_api_key=None,
        deepseek_model="deepseek-v4-flash",
        smtp_host=None,
        smtp_port=587,
        smtp_user=None,
        smtp_password=None,
        brief_from_email=None,
        brief_to_email=None,
        timezone="Asia/Hong_Kong",
        run_mode="sample",
        market_data_mode="sample",
        calendar_mode="sample",
        theme_source_mode="sample",
        output_dir=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
    )

    def fake_replace_theme(data):
        return replace_theme_radar_with_live(
            data,
            client_factory=FakeThemeClient,
            sources=_theme_sources(),
        )

    monkeypatch.setattr(runner_module, "replace_theme_radar_with_live", fake_replace_theme)

    result = run_brief(settings, send=False, live_theme_radar=True)
    log_event = json.loads(result.log_path.read_text(encoding="utf-8"))

    assert log_event["theme_data"]["mode"] == "live_with_fallback"
    assert log_event["theme_data"]["candidate_count"] == 2
    assert log_event["theme_data"]["fallback_used"] is False
    assert "Why exclude food and energy from inflation measures?" in log_event["theme_data"]["selected_titles"]
