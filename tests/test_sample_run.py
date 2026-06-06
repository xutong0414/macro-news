from __future__ import annotations

import json
from dataclasses import replace
from datetime import date

from macro_news.config import Settings, normalize_timezone
from macro_news.costing import TokenUsage
from macro_news.llm import SynthesisResult, parse_narrative_response
from macro_news.market_data import replace_market_rows_with_live
from macro_news.render import render_markdown
import macro_news.runner as runner_module
from macro_news.runner import run_brief
from macro_news.sample_data import build_sample_brief_data


def _word_count(text: str) -> int:
    return len(text.split())


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
    def __init__(self, payload):
        self.payload = payload

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
