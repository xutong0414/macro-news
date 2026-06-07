from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from macro_news.config import Settings, normalize_timezone
from macro_news.costing import TokenUsage
from macro_news.llm import SynthesisResult, parse_narrative_response
from macro_news.market_data import replace_market_rows_with_live
from macro_news.portfolio import active_positions, apply_portfolio_assumptions, read_position_entries
from macro_news.render import render_html, render_markdown
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


def test_portfolio_positions_carry_forward(tmp_path) -> None:
    path = tmp_path / "positions.csv"
    path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,quantity,unit,notes",
                "2026-06-01,USD/JPY,long,high,,,Assignment assumption",
                "2026-06-01,Gold,overweight,medium,,,Assignment assumption",
                "2026-06-10,Gold,neutral,low,,,Risk reduced",
            ]
        ),
        encoding="utf-8",
    )

    entries = read_position_entries(path)
    active = active_positions(entries, date(2026, 6, 12))
    active_by_asset = {entry.asset: entry for entry in active}
    data = apply_portfolio_assumptions(build_sample_brief_data(), run_date=date(2026, 6, 12), path=path)

    assert active_by_asset["USD/JPY"].position == "long"
    assert active_by_asset["Gold"].position == "neutral"
    assert any("USD/JPY: long" in item for item in data.assumptions)
    assert any("Gold: neutral" in item for item in data.assumptions)
    assert any("carry-forward rule" in item.lower() for item in data.assumptions)


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
    assert "Dashboard notes:" in brief
    assert "| Asset | Close | Prior | Change | As of | Status | Reading |" in brief
    assert "| Session | Event date | Time | Event | Consensus | Status | Why it matters |" in brief
    assert "| Asset | Close | Prior | Change | So what |" not in brief
    assert "### 1. USD/JPY Intervention Risk" in brief
    assert "momentum.\n\n**So what:** keep the FX view" in brief
    assert "**Read more:** [Yahoo Finance](https://finance.yahoo.com/search?p=USD+JPY+Japan+intervention+yield+spread)" in brief
    assert "![USD/JPY in Five Days](chart.png)" in brief
    assert "**Reading:** This chart supports the first thing that matters today (see above)." in brief
    assert "Source depth: Sample scaffold" in brief
    assert "Caption:" not in brief
    assert "EUR/USD" in brief
    assert "Germany 10Y yield" not in brief


def test_sample_brief_html_renders_chart_reading_label() -> None:
    html = render_html(build_sample_brief_data())

    assert 'alt="USD/JPY in Five Days"' in html
    assert '<p class="reading"><strong>Reading:</strong> This chart supports the first thing that matters today (see above).' in html
    assert "Caption:" not in html


def test_three_things_japan_yield_item_gets_rates_title() -> None:
    data = replace(
        build_sample_brief_data(),
        three_things=[
            "USD/JPY is near the intervention zone after a large rise. So what: keep the long USD/JPY risk tightly monitored.",
            "US 10Y yields rose while Japan 10Y yields also increased and DXY gained. So what: EM debt faces pressure from rates and dollar strength.",
            "Equities are softer and oil is lower. So what: treat riskier exposures cautiously.",
        ],
    )
    brief = render_markdown(data)

    assert "### 2. Rates And Dollar Pressure" in brief


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
        "USD/JPY is near the intervention zone after a large rise. So what: keep the long USD/JPY risk tightly monitored.",
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
      "contrarian_corner": "The market may be too relaxed about the idea that policy easing can arrive without a renewed inflation problem. If oil, freight, or shelter data firm while Treasury supply keeps term premium elevated, the next surprise is higher US yields rather than weaker growth. That would support the dollar and challenge duration-heavy trades."
    }
    """

    generated = parse_narrative_response(response, base)

    assert generated.market_rows == base.market_rows
    assert generated.calendar == base.calendar
    assert generated.chart_series == base.chart_series
    assert generated.three_things[0].startswith("USD/JPY")
    assert generated.theme_radar[0].summary.startswith("The author argues")
    assert generated.contrarian_corner.startswith("The market may be")
    assert "gemini_synthesis" in generated.data_sources


def test_parse_narrative_response_rejects_usdjpy_portfolio_logic_error() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "The DXY climbed and dollar strength is a direct risk to our long USD/JPY position. So what: this should fail because the portfolio logic is backwards.",
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
      "contrarian_corner": "The market may be too relaxed about the idea that policy easing can arrive without a renewed inflation problem. If oil, freight, or shelter data firm while Treasury supply keeps term premium elevated, the next surprise is higher US yields rather than weaker growth. That would support the dollar and challenge duration-heavy trades."
    }
    """

    try:
        parse_narrative_response(response, base)
    except ValueError as exc:
        assert "dollar strength" in str(exc)
    else:
        raise AssertionError("Expected USD/JPY portfolio logic validation to fail")


def test_parse_narrative_response_requires_first_item_to_support_chart() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "Gold is lower as rates rise. So what: the gold overweight needs tighter risk monitoring.",
        "USD/JPY is near the intervention zone after a large rise. So what: keep the long USD/JPY risk tightly monitored.",
        "Equities are softer and the dollar is firmer. So what: EM debt exposure should be treated carefully."
      ],
      "theme_radar": [
        {
          "title": "The term premium refuses to disappear",
          "source": "Sample macro research note",
          "link": "https://example.com/research/term-premium",
          "summary": "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. The point is not that growth is suddenly stronger, but that investors want more compensation for duration risk when supply headlines keep returning. The note says duration risk remains central.",
          "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring."
        }
      ],
      "contrarian_corner": "The simple read is that USD/JPY can keep rising while US yields stay high and the dollar is firm. A trigger that would challenge this view is a direct warning from Japanese officials that forces investors to reassess yen-reversal risk and reduce exposure before the next policy headline."
    }
    """

    try:
        parse_narrative_response(response, base)
    except ValueError as exc:
        assert "chart-support item" in str(exc)
    else:
        raise AssertionError("Expected first-item chart-support validation to fail")


def test_parse_narrative_response_trims_long_three_things_item() -> None:
    base = build_sample_brief_data()
    long_item = (
        "USD / JPY is near the intervention zone after a large rise, and the market discussion around the pair is now focused on "
        "whether officials become more uncomfortable with the level, pace, and persistence of yen weakness, while US yields and "
        "Japan yields both remain important background signals after the US 10Y moved to 4. 54 % and should be monitored carefully through the session. "
        "So what: keep the long USD/JPY risk tightly monitored because a sudden official warning or intervention headline could reverse gains quickly."
    )
    response = f"""
    {{
      "three_things": [
        {json.dumps(long_item)},
        "WTI oil rose 1.7%, adding another inflation signal to the morning tape. So what: EM debt exposure should be treated carefully.",
        "Gold is lower as rates rise. So what: the gold overweight needs tighter risk monitoring."
      ],
      "theme_radar": [
        {{
          "title": "The term premium refuses to disappear",
          "source": "Sample macro research note",
          "link": "https://example.com/research/term-premium",
          "summary": "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. The point is not that growth is suddenly stronger, but that investors want more compensation for duration risk when supply headlines keep returning.",
          "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring."
        }}
      ],
      "contrarian_corner": "The simple read is that USD/JPY can keep rising while US yields stay high and the dollar is firm. A trigger that would challenge this view is a direct warning from Japanese officials that forces investors to reassess yen-reversal risk and reduce exposure before the next policy headline."
    }}
    """

    generated = parse_narrative_response(response, base)

    assert _word_count(generated.three_things[0]) <= 80
    assert "So what:" in generated.three_things[0]
    assert "USD / JPY" not in generated.three_things[0]
    assert "4. 54 %" not in generated.three_things[0]
    assert "4.54%" in generated.three_things[0]


def test_parse_narrative_response_rejects_japan_yield_carry_error() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "Higher Japanese yields reinforce the carry advantage for USD/JPY. So what: keep the long USD/JPY trade as the clean expression.",
        "Gold is lower as rates rise. So what: the gold overweight needs tighter risk monitoring.",
        "Equities are softer and the dollar is firmer. So what: EM debt exposure should be treated carefully."
      ],
      "theme_radar": [
        {
          "title": "The term premium refuses to disappear",
          "source": "Sample macro research note",
          "link": "https://example.com/research/term-premium",
          "summary": "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is a mix of auction tails, dealer balance-sheet constraints, and resilient breakevens. This is not a simple growth story; it is about the market demanding more compensation for duration risk. The note also says positioning has not fully adjusted, leaving rallies vulnerable when supply headlines return.",
          "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring."
        }
      ],
      "contrarian_corner": "The consensus narrative is that higher yields and dollar strength make the USD/JPY long straightforward. A trigger that would challenge this view is coordinated Japanese verbal intervention or a hawkish BOJ signal that makes yen shorts look crowded."
    }
    """

    try:
        parse_narrative_response(response, base)
    except ValueError as exc:
        assert "Japan yields" in str(exc)
    else:
        raise AssertionError("Expected Japan yield carry validation to fail")


def test_parse_narrative_response_rejects_unsupported_market_pricing_claim() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "USD/JPY is near the intervention zone after a large rise. So what: keep the long USD/JPY risk tightly monitored.",
        "Gold is lower as rates rise. So what: the gold overweight needs tighter risk monitoring.",
        "Equities are softer and the dollar is firmer. So what: EM debt exposure should be treated carefully."
      ],
      "theme_radar": [
        {
          "title": "The term premium refuses to disappear",
          "source": "Sample macro research note",
          "link": "https://example.com/research/term-premium",
          "summary": "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. The point is not that growth is suddenly stronger, but that investors want more compensation for duration risk when supply headlines keep returning. The note says duration risk remains central.",
          "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring."
        }
      ],
      "contrarian_corner": "The simple read is that USD/JPY can keep rising while US yields stay high and the dollar is firm. However, the market is increasingly pricing in intervention risk as spot nears 160. A trigger that would challenge the trend is a direct warning from Japanese officials that forces traders to reassess yen-reversal risk."
    }
    """

    try:
        parse_narrative_response(response, base)
    except ValueError as exc:
        assert "unsupported market-positioning language" in str(exc)
    else:
        raise AssertionError("Expected unsupported market-pricing validation to fail")


def test_parse_narrative_response_rejects_unsupported_spread_claim() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "Japan yields rose and the narrowing US-Japan yield spread adds risk to USD/JPY. So what: keep the long USD/JPY risk tightly monitored.",
        "Gold is lower as rates rise. So what: the gold overweight needs tighter risk monitoring.",
        "Equities are softer and the dollar is firmer. So what: EM debt exposure should be treated carefully."
      ],
      "theme_radar": [
        {
          "title": "The term premium refuses to disappear",
          "source": "Sample macro research note",
          "link": "https://example.com/research/term-premium",
          "summary": "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. The point is not that growth is suddenly stronger, but that investors want more compensation for duration risk when supply headlines keep returning. The note says duration risk remains central.",
          "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring."
        }
      ],
      "contrarian_corner": "The simple read is that USD/JPY can keep rising while US yields stay high and the dollar is firm. A trigger that would challenge this view is a direct warning from Japanese officials that forces investors to reassess yen-reversal risk and reduce exposure before the next policy headline."
    }
    """

    try:
        parse_narrative_response(response, base)
    except ValueError as exc:
        assert "unsupported market-positioning language" in str(exc)
    else:
        raise AssertionError("Expected unsupported spread validation to fail")


def test_parse_narrative_response_rejects_mismatched_market_number() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "USD/JPY is near the intervention zone after a large rise. So what: keep the long USD/JPY risk tightly monitored.",
        "WTI oil fell 3.1%, adding another risk-off signal to the morning tape. So what: EM debt exposure should be treated carefully.",
        "Gold is lower as rates rise. So what: the gold overweight needs tighter risk monitoring."
      ],
      "theme_radar": [
        {
          "title": "The term premium refuses to disappear",
          "source": "Sample macro research note",
          "link": "https://example.com/research/term-premium",
          "summary": "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. The point is not that growth is suddenly stronger, but that investors want more compensation for duration risk when supply headlines keep returning. The note says duration risk remains central.",
          "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring."
        }
      ],
      "contrarian_corner": "The simple read is that USD/JPY can keep rising while US yields stay high and the dollar is firm. A trigger that would challenge this view is a direct warning from Japanese officials that forces investors to reassess yen-reversal risk and reduce exposure before the next policy headline."
    }
    """

    try:
        parse_narrative_response(response, base)
    except ValueError as exc:
        assert "WTI oil" in str(exc)
        assert "dashboard row change" in str(exc)
    else:
        raise AssertionError("Expected mismatched market-number validation to fail")


def test_parse_narrative_response_rejects_change_at_price_language() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "USD/JPY is trading near elevated levels, with the pair's change flat at 157.20. So what: keep the long USD/JPY risk tightly monitored.",
        "WTI oil rose 1.7%, adding another inflation signal to the morning tape. So what: EM debt exposure should be treated carefully.",
        "Gold is lower as rates rise. So what: the gold overweight needs tighter risk monitoring."
      ],
      "theme_radar": [
        {
          "title": "The term premium refuses to disappear",
          "source": "Sample macro research note",
          "link": "https://example.com/research/term-premium",
          "summary": "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. The point is not that growth is suddenly stronger, but that investors want more compensation for duration risk when supply headlines keep returning. The note says duration risk remains central.",
          "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring."
        }
      ],
      "contrarian_corner": "The simple read is that USD/JPY can keep rising while US yields stay high and the dollar is firm. A trigger that would challenge this view is a direct warning from Japanese officials that forces investors to reassess yen-reversal risk and reduce exposure before the next policy headline."
    }
    """

    try:
        parse_narrative_response(response, base)
    except ValueError as exc:
        assert "unsupported market-positioning language" in str(exc)
    else:
        raise AssertionError("Expected change-at-price validation to fail")


def test_parse_narrative_response_rejects_generic_theme_openers() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "USD/JPY is near the intervention zone after a large rise. So what: keep the long USD/JPY risk tightly monitored.",
        "WTI oil rose 1.7%, adding another inflation signal to the morning tape. So what: EM debt exposure should be treated carefully.",
        "Gold is lower as rates rise. So what: the gold overweight needs tighter risk monitoring."
      ],
      "theme_radar": [
        {
          "title": "The term premium refuses to disappear",
          "source": "Sample macro research note",
          "link": "https://example.com/research/term-premium",
          "summary": "This analysis explores how fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. The point is not that growth is suddenly stronger, but that investors want more compensation for duration risk when supply headlines keep returning. The note says duration risk remains central.",
          "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring."
        }
      ],
      "contrarian_corner": "The simple read is that USD/JPY can keep rising while US yields stay high and the dollar is firm. A trigger that would challenge this view is a direct warning from Japanese officials that forces investors to reassess yen-reversal risk and reduce exposure before the next policy headline."
    }
    """

    try:
        parse_narrative_response(response, base)
    except ValueError as exc:
        assert "generic phrasing" in str(exc)
    else:
        raise AssertionError("Expected generic Theme Radar opener validation to fail")


def test_parse_narrative_response_strips_theme_summary_so_what() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "USD/JPY is near the intervention zone after a large rise. So what: keep the long USD/JPY risk tightly monitored.",
        "WTI oil rose 1.7%, adding another inflation signal to the morning tape. So what: EM debt exposure should be treated carefully.",
        "Gold is lower as rates rise. So what: the gold overweight needs tighter risk monitoring."
      ],
      "theme_radar": [
        {
          "title": "The term premium refuses to disappear",
          "source": "Sample macro research note",
          "link": "https://example.com/research/term-premium",
          "summary": "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. The point is not that growth is suddenly stronger, but that investors want more compensation for duration risk when supply headlines keep returning. The note adds that duration risk remains central when supply pressure keeps returning. The selector picked it because the feed discusses rates and credit. So what: USD/JPY can keep support, but gold needs close monitoring.",
          "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring."
        }
      ],
      "contrarian_corner": "The simple read is that USD/JPY can keep rising while US yields stay high and the dollar is firm. A trigger that would challenge this view is a direct warning from Japanese officials that forces investors to reassess yen-reversal risk and reduce exposure before the next policy headline."
    }
    """

    generated = parse_narrative_response(response, base)

    assert "So what:" not in generated.theme_radar[0].summary
    assert "selector picked" not in generated.theme_radar[0].summary.lower()
    assert generated.theme_radar[0].summary.endswith("supply pressure keeps returning.")


def test_parse_narrative_response_rejects_unsourced_open_and_real_rate_language() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "USD/JPY is near the intervention zone after a large rise. So what: keep the long USD/JPY risk tightly monitored.",
        "Equities opened softer, with risk appetite weaker across regions. So what: EM debt exposure should be treated carefully.",
        "Gold fell 0.8% as real rates rose. So what: the gold overweight needs tighter risk monitoring."
      ],
      "theme_radar": [
        {
          "title": "The term premium refuses to disappear",
          "source": "Sample macro research note",
          "link": "https://example.com/research/term-premium",
          "summary": "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. The point is not that growth is suddenly stronger, but that investors want more compensation for duration risk when supply headlines keep returning. The note says duration risk remains central.",
          "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring."
        }
      ],
      "contrarian_corner": "The simple read is that USD/JPY can keep rising while US yields stay high and the dollar is firm. A trigger that would challenge this view is a direct warning from Japanese officials that forces investors to reassess yen-reversal risk and reduce exposure before the next policy headline."
    }
    """

    try:
        parse_narrative_response(response, base)
    except ValueError as exc:
        assert "unsupported market-positioning language" in str(exc)
    else:
        raise AssertionError("Expected unsourced open/real-rate validation to fail")


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
        portfolio_path=tmp_path / "positions.csv",
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
        portfolio_path=tmp_path / "positions.csv",
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
    def __init__(self, payload=None, text="", content: bytes | None = None):
        self.payload = payload
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")

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
                                "timestamp": [1780358400, 1780444800],
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
            if params.get("from") == "EUR":
                return FakeResponse({"rates": {"2026-06-04": {"USD": 1.08}, "2026-06-05": {"USD": 1.09}}})
            return FakeResponse({"rates": {"2026-06-04": {"JPY": 158.0}, "2026-06-05": {"JPY": 159.0}}})
        if "mof.go.jp" in url:
            csv_text = (
                "base date,1Y,2Y,3Y,4Y,5Y,6Y,7Y,8Y,9Y,10Y,15Y,20Y,25Y,30Y,40Y\n"
                "R8.6.3,1.126,1.401,1.56,1.767,1.943,2.077,2.219,2.373,2.508,2.645,3.183,3.521,3.817,3.817,3.748\n"
                "R8.6.4,1.148,1.417,1.579,1.787,1.966,2.105,2.242,2.395,2.535,2.671,3.225,3.554,3.835,3.833,3.749\n"
            )
            return FakeResponse(text=csv_text, content=csv_text.encode("cp932"))
        if "coingecko" in url:
            return FakeResponse({"bitcoin": {"usd": 60000, "usd_24h_change": 2.0}})
        raise AssertionError(f"Unexpected URL: {url} {params}")


def test_live_market_data_replaces_rows_and_logs_fallback(tmp_path) -> None:
    base = build_sample_brief_data()
    result = replace_market_rows_with_live(
        base,
        run_date=date(2026, 6, 6),
        cache_path=tmp_path / "market.json",
        client_factory=FakeMarketClient,
    )

    row_by_asset = {row.asset: row for row in result.data.market_rows}

    assert "Germany 10Y yield" not in row_by_asset
    assert row_by_asset["S&P 500"].close == "102.00"
    assert row_by_asset["S&P 500"].change == "+2.0%"
    assert row_by_asset["S&P 500"].as_of
    assert row_by_asset["S&P 500"].status == "*"
    assert row_by_asset["S&P 500"].so_what == "Risk tone improved; EM beta has some support if rates and the dollar stay contained."
    assert row_by_asset["US 10Y yield"].change == "+5 bp"
    assert row_by_asset["US 10Y yield"].so_what.startswith("Higher Treasury yields pressure gold")
    assert row_by_asset["Japan 10Y yield"].close == "2.671%"
    assert row_by_asset["Japan 10Y yield"].change == "+3 bp"
    assert row_by_asset["Japan 10Y yield"].so_what == "Higher JGB yields put Japan-rate pressure on the long USD/JPY view; compare against the US yield move."
    assert row_by_asset["EUR/USD"].close == "1.0900"
    assert row_by_asset["EUR/USD"].change == "+0.9%"
    assert row_by_asset["USD/JPY"].close == "159.00"
    assert row_by_asset["BTC"].change == "+2.0%"
    assert row_by_asset["DXY"].close == ""
    assert row_by_asset["DXY"].prior == ""
    assert row_by_asset["DXY"].change == ""
    assert row_by_asset["DXY"].as_of == ""
    assert row_by_asset["DXY"].status == ""
    assert "DXY" in result.fallback_assets
    assert "DXY" in result.errors
    assert "frankfurter:EURUSD" in result.sources
    assert "mof_japan:jgbcm_10y" in result.sources
    assert "yahoo_chart:^GSPC" in result.sources
    assert result.cached_assets == []
    assert any("extracted at" in note for note in result.data.dashboard_notes)
    assert any("Additional information about timing" in note for note in result.data.dashboard_notes)
    assert any("[Japan MOF JGB yield CSV]" in note for note in result.data.dashboard_notes)
    assert any("rates (US/Japan 10Y)" in note for note in result.data.dashboard_notes)
    rendered = render_markdown(result.data)
    assert "Frankfurter FX rows use the latest published daily reference rate" in rendered
    assert "Source Status shows live, cached, or scaffold fallback rows" not in rendered
    assert "value cells are left blank" in rendered


class FailingMarketClient(FakeMarketClient):
    def get(self, url, params=None):
        if "finance/chart" in url:
            raise RuntimeError("simulated market outage")
        return super().get(url, params=params)


def test_live_market_data_uses_cached_real_rows_before_scaffold(tmp_path) -> None:
    base = build_sample_brief_data()
    cache_path = tmp_path / "market.json"

    first = replace_market_rows_with_live(
        base,
        run_date=date(2026, 6, 6),
        cache_path=cache_path,
        client_factory=FakeMarketClient,
    )
    second = replace_market_rows_with_live(
        base,
        run_date=date(2026, 6, 6),
        cache_path=cache_path,
        client_factory=FailingMarketClient,
    )

    second_rows = {row.asset: row for row in second.data.market_rows}

    assert first.live_assets
    assert "S&P 500" in second.cached_assets
    assert second_rows["S&P 500"].close == "102.00"
    assert second_rows["S&P 500"].status == "†"
    assert "S&P 500" not in second.fallback_assets
    assert "DXY" in second.fallback_assets


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
    assert event_by_name["USD Non-Farm Employment Change"].event_date == "2026-06-06"
    assert event_by_name["USD Non-Farm Employment Change"].status == "Live"
    assert event_by_name["EUR Core CPI Flash Estimate y/y"].session == "Europe"
    assert event_by_name["EUR Core CPI Flash Estimate y/y"].status == "Live"
    assert event_by_name["CNY RatingDog Manufacturing PMI"].session == "Asia"
    assert event_by_name["CNY RatingDog Manufacturing PMI"].event_date == "2026-06-07"
    assert event_by_name["CNY RatingDog Manufacturing PMI"].status == "*"
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
    assert result.data.calendar[0].event_date == "2026-06-06"
    assert result.data.calendar[0].status == "†"
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
        portfolio_path=tmp_path / "positions.csv",
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
    assert all(45 <= _word_count(item.summary) <= 100 for item in result.data.theme_radar)
    assert all(item.link.startswith("https://") for item in result.data.theme_radar)
    assert all(item.source_depth == "RSS excerpt" for item in result.data.theme_radar)


def test_live_theme_radar_leaves_section_blank_when_sources_fail() -> None:
    base = build_sample_brief_data()
    result = replace_theme_radar_with_live(
        base,
        client_factory=FailingThemeClient,
        sources=_theme_sources(),
    )

    assert result.data.theme_radar == []
    assert result.fallback_used is True
    assert result.candidate_count == 0
    assert "theme_feed:test_fred" in result.errors
    assert "theme_feed:test_liberty" in result.errors
    assert any("section left blank" in note for note in result.data.source_notes)


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
        portfolio_path=tmp_path / "positions.csv",
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
