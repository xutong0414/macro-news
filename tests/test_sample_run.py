from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from macro_news.config import Settings, normalize_timezone
from macro_news.costing import TokenUsage
from macro_news.llm import SynthesisResult, build_narrative_prompt, build_section_fallback_narrative, parse_narrative_response
import macro_news.model_compare as model_compare_module
from macro_news.model_compare import compare_gemini_models
from macro_news.market_data import replace_market_rows_with_live
from macro_news.portfolio import active_positions, apply_portfolio_assumptions, read_position_entries
from macro_news.render import render_html, render_markdown
import macro_news.runner as runner_module
from macro_news.calendar_data import replace_calendar_with_live
from macro_news.runner import run_brief
from macro_news.sample_data import CalendarEvent, MarketRow, ThemeItem, build_sample_brief_data
from macro_news.theme_data import (
    THEME_RULES,
    ThemeCandidate,
    ThemeSearchQuery,
    ThemeSource,
    _extract_article_text,
    parse_feed,
    replace_theme_radar_with_live,
    select_theme_candidates,
)
from macro_news.topic_selection import _theme_source_score, select_portfolio_topics


def _word_count(text: str) -> int:
    return len(text.split())


def _words(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}{index}" for index in range(count))


def _calendar_reference_now() -> datetime:
    return datetime(2026, 6, 6, 0, 0, tzinfo=ZoneInfo("Asia/Hong_Kong"))


def _valid_response_with_first_thing(first_thing: str) -> str:
    return json.dumps(
        {
            "three_things": [
                first_thing,
                "USD/JPY is near the intervention zone after a large rise. So what: keep the long USD/JPY risk tightly monitored.",
                "Equities are softer and the dollar is firmer. So what: EM debt exposure should be treated carefully.",
            ],
            "theme_radar": [
                {
                    "title": "The term premium refuses to disappear",
                    "source": "Sample macro research note",
                    "link": "https://example.com/research/term-premium",
                    "summary": "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. Investors want more compensation for duration risk when supply headlines keep returning, so rallies remain fragile.",
                    "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring.",
                }
            ],
            "contrarian_corner": "The simple read is that USD/JPY can keep rising while US yields stay high and the dollar is firm. A trigger that would challenge this view is a direct warning from Japanese officials that forces investors to reassess yen-reversal risk and reduce exposure before the next policy headline.",
        }
    )


def _assert_first_thing_rejected(base, first_thing: str, expected_message: str) -> None:
    try:
        parse_narrative_response(_valid_response_with_first_thing(first_thing), base)
    except ValueError as exc:
        assert expected_message in str(exc)
    else:
        raise AssertionError(f"Expected narrative validation to fail: {expected_message}")


def test_parse_narrative_response_ignores_trailing_non_json_junk() -> None:
    response = _valid_response_with_first_thing(
        "USD/JPY is near the intervention zone after a large rise. So what: keep the long USD/JPY risk tightly monitored."
    )
    response_with_junk = f"{response}\n  }}\n]"

    generated = parse_narrative_response(response_with_junk, build_sample_brief_data())

    assert generated.three_things[0].startswith("USD/JPY is near the intervention zone")


def test_timezone_aliases_normalize() -> None:
    assert normalize_timezone("Hong Kong") == "Asia/Hong_Kong"
    assert normalize_timezone("HongKong") == "Asia/Hong_Kong"
    assert normalize_timezone("Asia/Hong Kong") == "Asia/Hong_Kong"
    assert normalize_timezone("Asia/Shanghai") == "Asia/Shanghai"


def test_theme_article_fetch_limit_env_falls_back_to_metadata_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("THEME_METADATA_FETCH_LIMIT", "3")
    monkeypatch.delenv("THEME_ARTICLE_FETCH_LIMIT", raising=False)

    assert Settings.from_env().theme_article_fetch_limit == 3

    monkeypatch.setenv("THEME_ARTICLE_FETCH_LIMIT", "0")

    assert Settings.from_env().theme_article_fetch_limit == 0


def test_live_run_filters_replaced_sample_source_labels() -> None:
    sources = [
        "sample_market_data",
        "sample_calendar",
        "sample_deep_content",
        "yahoo_chart:^GSPC",
        "faireconomy:ff_calendar_thisweek",
        "theme_feed:bank_underground",
        "gemini_synthesis",
    ]

    filtered = runner_module._effective_data_sources(
        sources,
        live_market_data=True,
        live_calendar=True,
        live_theme_radar=True,
    )

    assert filtered == [
        "yahoo_chart:^GSPC",
        "faireconomy:ff_calendar_thisweek",
        "theme_feed:bank_underground",
        "gemini_synthesis",
    ]


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


def test_portfolio_positions_read_significance_column(tmp_path) -> None:
    path = tmp_path / "positions.csv"
    path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,significance,quantity,unit,notes",
                "2026-06-01,US AI semiconductors basket,overweight,medium,high,,,AI capex proxy",
            ]
        ),
        encoding="utf-8",
    )

    entries = read_position_entries(path)
    data = apply_portfolio_assumptions(build_sample_brief_data(), run_date=date(2026, 6, 12), path=path)

    assert entries[0].significance == "high"
    assert any("significance=high" in item for item in data.assumptions)


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
    assert "| Asset | Close | Prior | Change | As of | Reading |" in brief
    assert "| Asset | Close | Prior | Change | As of | Status | Reading |" not in brief
    assert "| Session | Event date | Time | Event | Consensus | Status | Why it matters |" in brief
    assert "| Asset | Close | Prior | Change | So what |" not in brief
    assert "### 1. USD/JPY Intervention Risk" in brief
    assert "momentum.\n\n**So what:** keep the FX view" in brief
    assert "**Read more:** [Yahoo Finance currencies](https://finance.yahoo.com/markets/currencies/)" in brief
    assert "![USD/JPY: 3-Month Trend](chart.png)" in brief
    assert "the latest five observations are highlighted" in brief
    assert "**Data source:** sample USD/JPY series" in brief
    assert "Source depth: Sample scaffold" in brief
    assert "**For Our Book:** duration pressure supports USD/JPY" in brief
    assert "## Feedback Questionnaire" in brief
    assert "Usefulness 1-5" in brief
    assert "| Dashboard | Overnight market dashboard |" in brief
    assert "| Dashboard | S&P 500 |" not in brief
    assert "Feedback date:" not in brief
    assert "keep / deprioritize / drop / rewrite" not in brief
    assert "### Portfolio / Book" in brief
    assert "### Data Handling" in brief
    assert "Caption:" not in brief
    assert "EUR/USD" in brief
    assert "Germany 10Y yield" not in brief


def test_sample_brief_html_renders_chart_reading_label() -> None:
    html = render_html(build_sample_brief_data())

    assert 'alt="USD/JPY: 3-Month Trend"' in html
    assert '<p class="reading"><strong>Reading:</strong> This chart supports the first thing that matters today (see above); the latest five observations are highlighted.' in html
    assert '<p class="read-more"><strong>Data source:</strong> sample USD/JPY series</p>' in html
    assert '<strong>For Our Book:</strong>' in html
    assert '<p class="note-line"><strong>So what:</strong>' in html
    assert '<p class="read-more"><strong>Read more:</strong>' in html
    assert '<p class="footnote-heading">Dashboard notes:</p>' in html
    assert '<p class="footnote">- Dashboard scope:' in html
    assert "Caption:" not in html


def test_theme_radar_empty_section_is_explicit() -> None:
    brief = render_markdown(replace(build_sample_brief_data(), theme_radar=[]))

    assert "No verified Theme Radar items are available for this run; no replacement items were generated." in brief


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


def test_parse_narrative_response_accepts_structured_three_things() -> None:
    base = build_sample_brief_data()
    response = json.dumps(
        {
            "three_things": [
                {
                    "body": "USD/JPY is near the intervention zone after a large rise.",
                    "so_what": "keep the long USD/JPY risk tightly monitored.",
                },
                {
                    "body": "WTI oil rose 1.7%, adding another inflation signal to the morning tape.",
                    "so_what": "EM debt exposure should be treated carefully.",
                },
                {
                    "body": "Gold is lower as rates rise.",
                    "so_what": "the gold overweight needs tighter risk monitoring.",
                },
            ],
            "theme_radar": [
                {
                    "title": "The term premium refuses to disappear",
                    "source": "Sample macro research note",
                    "link": "https://example.com/research/term-premium",
                    "summary": "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. Investors want more compensation for duration risk when supply headlines keep returning, so rallies remain fragile.",
                    "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring.",
                }
            ],
            "contrarian_corner": "The simple read is that USD/JPY can keep rising while US yields stay high and the dollar is firm. A trigger that would challenge this view is a direct warning from Japanese officials that forces investors to reassess yen-reversal risk and reduce exposure before the next policy headline.",
        }
    )

    generated = parse_narrative_response(response, base)

    assert generated.three_things[0] == (
        "USD/JPY is near the intervention zone after a large rise. "
        "So what: keep the long USD/JPY risk tightly monitored."
    )
    assert generated.three_things[0].count("So what:") == 1


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


def test_parse_narrative_response_allows_selected_non_usdjpy_first_topic() -> None:
    base = replace(
        build_sample_brief_data(),
        topic_candidates=[
            {"title": "Oil And Inflation Risk", "required_terms": ["oil", "brent", "wti"]},
            {"title": "USD/JPY Intervention Risk", "required_terms": ["usd/jpy", "yen", "intervention"]},
            {"title": "Gold And Rates Pressure", "required_terms": ["gold", "rates", "yield"]},
        ],
        three_thing_titles=["Oil And Inflation Risk", "USD/JPY Intervention Risk", "Gold And Rates Pressure"],
        chart_title="Brent oil: 3-Month Trend",
    )
    response = """
    {
      "three_things": [
        "WTI oil rose 1.7%, adding another inflation signal to the morning tape. So what: EM debt exposure should be treated carefully.",
        "USD/JPY is near the intervention zone after a large rise. So what: keep the long USD/JPY risk tightly monitored.",
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
      "contrarian_corner": "The simple read is that oil strength keeps inflation pressure alive and delays rate relief. A trigger that would challenge this view is a sharp reversal in Brent and WTI after an inventory or demand report, which would make the inflation impulse look temporary and reduce pressure on EM duration."
    }
    """

    generated = parse_narrative_response(response, base)

    assert generated.three_things[0].startswith("WTI oil")
    assert generated.chart_title == "Brent oil: 3-Month Trend"


def test_parse_narrative_response_requires_selected_topic_order() -> None:
    base = replace(
        build_sample_brief_data(),
        topic_candidates=[
            {"title": "Oil And Inflation Risk", "required_terms": ["oil", "brent", "wti"]},
            {"title": "USD/JPY Intervention Risk", "required_terms": ["usd/jpy", "yen", "intervention"]},
            {"title": "Gold And Rates Pressure", "required_terms": ["gold", "rates", "yield"]},
        ],
        three_thing_titles=["Oil And Inflation Risk", "USD/JPY Intervention Risk", "Gold And Rates Pressure"],
    )
    response = """
    {
      "three_things": [
        "Gold is lower as rates rise. So what: the gold overweight needs tighter risk monitoring.",
        "USD/JPY is near the intervention zone after a large rise. So what: keep the long USD/JPY risk tightly monitored.",
        "WTI oil rose 1.7%, adding another inflation signal to the morning tape. So what: EM debt exposure should be treated carefully."
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
        assert "selected topic: Oil And Inflation Risk" in str(exc)
    else:
        raise AssertionError("Expected selected-topic validation to fail")


def test_parse_narrative_response_requires_contrarian_to_follow_first_topic() -> None:
    base = replace(
        build_sample_brief_data(),
        topic_candidates=[
            {"title": "Oil And Inflation Risk", "required_terms": ["oil", "brent", "wti"]},
            {"title": "USD/JPY Intervention Risk", "required_terms": ["usd/jpy", "yen", "intervention"]},
            {"title": "Gold And Rates Pressure", "required_terms": ["gold", "rates", "yield"]},
        ],
        three_thing_titles=["Oil And Inflation Risk", "USD/JPY Intervention Risk", "Gold And Rates Pressure"],
    )
    response = """
    {
      "three_things": [
        "WTI oil rose 1.7%, adding another inflation signal to the morning tape. So what: EM debt exposure should be treated carefully.",
        "USD/JPY is near the intervention zone after a large rise. So what: keep the long USD/JPY risk tightly monitored.",
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
        assert "contrarian_corner must challenge the first selected topic" in str(exc)
    else:
        raise AssertionError("Expected contrarian topic validation to fail")


def test_portfolio_topic_selection_can_change_chart_from_usdjpy(tmp_path) -> None:
    portfolio_path = tmp_path / "positions.csv"
    portfolio_path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,quantity,unit,notes",
                "2026-06-01,USD/JPY,long,high,,,Assignment assumption",
                "2026-06-11,Brent oil,watch,medium,,,Inflation proxy",
            ]
        ),
        encoding="utf-8",
    )
    data = build_sample_brief_data()
    data = replace(
        data,
        market_rows=[
            *data.market_rows,
            MarketRow("Brent oil", "$92.00", "$89.00", "+3.4%", "Brent strength adds global inflation risk and keeps geopolitical risk premium in focus."),
        ],
        market_series={
            "Brent oil": tuple((f"2026-06-{day:02d}", 88.0 + day / 2) for day in range(1, 12)),
            "USD/JPY": tuple(data.chart_series),
        },
    )

    selected = select_portfolio_topics(data, run_date=date(2026, 6, 11), portfolio_path=portfolio_path)

    assert selected.three_thing_titles[0] == "Oil And Inflation Risk"
    assert selected.chart_title == "Brent oil: 3-Month Trend"
    assert selected.chart_source_url == "https://finance.yahoo.com/quote/BZ=F/"


def test_topic_selection_can_rank_calendar_event_ahead_of_market_move(tmp_path) -> None:
    portfolio_path = tmp_path / "positions.csv"
    portfolio_path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,quantity,unit,notes",
                "2026-06-01,US 10Y yield,short duration,medium,,,Rates risk",
                "2026-06-01,Gold,overweight,medium,,,Inflation hedge",
            ]
        ),
        encoding="utf-8",
    )
    data = replace(
        build_sample_brief_data(),
        market_rows=[
            MarketRow("US 10Y yield", "4.42%", "4.42%", "+0 bp", "Treasuries are not moving the story; watch dollar and commodity signals instead."),
            MarketRow("Gold", "$2,352", "$2,351", "+0.0%", "Gold is holding steady; rates and DXY will decide whether the overweight has cover."),
            MarketRow("DXY", "104.8", "104.8", "+0.0%", "The dollar is not adding a fresh shock; pair-specific FX moves matter more today."),
        ],
        calendar=[
            CalendarEvent("US", "20:30 HKT", "USD Core CPI m/m", "0.3%", "Inflation surprise can reprice rates, dollar direction, and gold.", "2026-06-11", "Live", "https://www.forexfactory.com/calendar?day=jun11.2026"),
        ],
    )

    selected = select_portfolio_topics(data, run_date=date(2026, 6, 11), portfolio_path=portfolio_path)

    assert selected.topic_candidates[0]["origin"] == "calendar"
    assert selected.three_thing_titles[0] == "US Inflation Event Risk"


def test_topic_selection_prefers_direct_calendar_portfolio_link(tmp_path) -> None:
    portfolio_path = tmp_path / "positions.csv"
    portfolio_path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,quantity,unit,notes",
                "2026-06-01,USD/JPY,long,high,,,Assignment assumption",
                "2026-06-01,EUR/USD,watch,low,,,Policy-divergence monitor",
            ]
        ),
        encoding="utf-8",
    )
    data = replace(
        build_sample_brief_data(),
        market_rows=[],
        calendar=[
            CalendarEvent(
                "Europe",
                "20:15 HKT",
                "EUR Main Refinancing Rate",
                "2.40%",
                "High-impact EUR event for rates, FX, and risk appetite.",
                "2026-06-11",
                "Live",
                "https://www.forexfactory.com/calendar?day=jun11.2026",
            ),
        ],
        theme_radar=[],
    )

    selected = select_portfolio_topics(data, run_date=date(2026, 6, 11), portfolio_path=portfolio_path)

    assert selected.three_thing_titles[0] == "ECB Policy Event Risk"
    assert selected.topic_candidates[0]["portfolio_asset"] == "EUR/USD"
    assert selected.topic_candidates[0]["score_components"]["direct_portfolio_link"] > 0


def test_topic_selection_adds_em_debt_dxy_guardrails(tmp_path) -> None:
    portfolio_path = tmp_path / "positions.csv"
    portfolio_path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,quantity,unit,notes",
                "2026-06-01,EM debt basket,exposed,medium,,,Assignment assumption",
            ]
        ),
        encoding="utf-8",
    )
    data = replace(
        build_sample_brief_data(),
        market_rows=[
            MarketRow("US 10Y yield", "4.52%", "4.54%", "-2 bp", "Lower Treasury yields ease pressure on EM duration."),
            MarketRow("DXY", "100.22", "99.95", "+0.3%", "Dollar strength tightens EM financing conditions."),
            MarketRow("S&P 500", "7,269", "7,266", "+0.1%", "US equities give little direction; rates and FX are the cleaner signal."),
            MarketRow("China internet / tech basket", "$26.04", "$26.44", "-1.5%", "China tech weakness flags softer China sentiment."),
        ],
        calendar=[],
        theme_radar=[],
    )

    selected = select_portfolio_topics(data, run_date=date(2026, 6, 11), portfolio_path=portfolio_path)
    topic = selected.topic_candidates[0]

    assert topic["title"] == "EM Debt Conditions"
    assert "DXY is up" in topic["narrative_guidance"]
    assert "tighter funding for EM debt" in topic["narrative_guidance"]
    assert "Do not say stronger DXY eases dollar pressure or helps EM debt." in topic["avoid_claims"]


def test_topic_selection_adds_global_dxy_guardrail_to_unrelated_topic(tmp_path) -> None:
    portfolio_path = tmp_path / "positions.csv"
    portfolio_path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,quantity,unit,notes",
                "2026-06-01,S&P 500,underweight,medium,,,Equity beta watch",
            ]
        ),
        encoding="utf-8",
    )
    data = replace(
        build_sample_brief_data(),
        market_rows=[
            MarketRow("S&P 500", "7,269", "7,250", "+0.3%", "US equities are firmer, a partial support for risk appetite."),
            MarketRow("Euro Stoxx 50", "6,067", "6,010", "+1.0%", "Eurozone risk appetite is firming."),
            MarketRow("VIX", "21.2", "22.2", "-4.6%", "Lower volatility supports risk appetite."),
            MarketRow("DXY", "100.22", "99.95", "+0.3%", "Dollar strength tightens EM financing conditions."),
        ],
        calendar=[],
        theme_radar=[],
    )

    selected = select_portfolio_topics(data, run_date=date(2026, 6, 11), portfolio_path=portfolio_path)
    topic = selected.topic_candidates[0]

    assert topic["title"] == "Equity Risk Tone"
    assert "Global dashboard guardrail: DXY is up" in topic["narrative_guidance"]
    assert "rising S&P 500 is a headwind" in topic["narrative_guidance"]
    assert any("Do not say broad dollar pressure eased" in claim for claim in topic["avoid_claims"])
    assert any("rising S&P 500 is a tailwind" in claim for claim in topic["avoid_claims"])


def test_theme_topic_gets_underweight_spx_guardrail_from_dashboard(tmp_path) -> None:
    portfolio_path = tmp_path / "positions.csv"
    portfolio_path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,quantity,unit,notes",
                "2026-06-01,S&P 500,underweight,medium,,,Equity beta watch",
            ]
        ),
        encoding="utf-8",
    )
    data = replace(
        build_sample_brief_data(),
        market_rows=[
            MarketRow("S&P 500", "7,269", "7,250", "+0.3%", "US equities are firmer, a partial support for risk appetite."),
            MarketRow("DXY", "100.22", "99.95", "+0.3%", "Dollar strength tightens EM financing conditions."),
        ],
        calendar=[],
        theme_radar=[
            ThemeItem(
                "Credit rationing for risky borrowers",
                "Liberty Street Economics",
                "https://example.com/credit",
                "The note says tighter credit availability for riskier borrowers can weigh on risk appetite and financial plumbing.",
                "What this means for our book: credit caution matters for equity beta.",
                "RSS content field + article metadata",
            )
        ],
    )

    selected = select_portfolio_topics(data, run_date=date(2026, 6, 11), portfolio_path=portfolio_path)
    credit_topic = next(topic for topic in selected.topic_candidates if topic["title"] == "Credit Conditions Signal")

    assert "rising S&P 500 is a headwind" in credit_topic["narrative_guidance"]
    assert any("underweight S&P 500" in claim for claim in credit_topic["avoid_claims"])


def test_topic_selection_adds_usdjpy_long_guardrails(tmp_path) -> None:
    portfolio_path = tmp_path / "positions.csv"
    portfolio_path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,quantity,unit,notes",
                "2026-06-01,USD/JPY,long,high,,,Assignment assumption",
            ]
        ),
        encoding="utf-8",
    )
    data = replace(
        build_sample_brief_data(),
        market_rows=[
            MarketRow("USD/JPY", "157.20", "156.10", "+0.7%", "The long is working, but extension raises intervention risk."),
            MarketRow("Japan 10Y yield", "2.67%", "2.65%", "+2 bp", "Higher JGB yields put Japan-rate pressure on the long USD/JPY view."),
            MarketRow("US 10Y yield", "4.42%", "4.36%", "+6 bp", "Higher Treasury yields keep dollar carry supported."),
            MarketRow("DXY", "104.8", "104.3", "+0.5%", "Dollar strength tightens EM financing conditions."),
        ],
        calendar=[],
        theme_radar=[],
    )

    selected = select_portfolio_topics(data, run_date=date(2026, 6, 11), portfolio_path=portfolio_path)
    topic = selected.topic_candidates[0]

    assert topic["title"] == "USD/JPY Intervention Risk"
    assert "long USD/JPY position is working" in topic["narrative_guidance"]
    assert "Japan-rate pressure separately" in topic["narrative_guidance"]
    assert any("Do not frame USD/JPY gains" in claim for claim in topic["avoid_claims"])


def test_narrative_prompt_includes_selected_topic_guardrails(tmp_path) -> None:
    portfolio_path = tmp_path / "positions.csv"
    portfolio_path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,quantity,unit,notes",
                "2026-06-01,EM debt basket,exposed,medium,,,Assignment assumption",
            ]
        ),
        encoding="utf-8",
    )
    data = replace(
        build_sample_brief_data(),
        market_rows=[
            MarketRow("US 10Y yield", "4.52%", "4.54%", "-2 bp", "Lower Treasury yields ease pressure on EM duration."),
            MarketRow("DXY", "100.22", "99.95", "+0.3%", "Dollar strength tightens EM financing conditions."),
            MarketRow("S&P 500", "7,269", "7,266", "+0.1%", "US equities give little direction; rates and FX are the cleaner signal."),
        ],
        calendar=[],
        theme_radar=[],
    )
    selected = select_portfolio_topics(data, run_date=date(2026, 6, 11), portfolio_path=portfolio_path)

    prompt = build_narrative_prompt(selected)

    assert "narrative_guidance" in prompt
    assert "avoid_claims" in prompt
    assert "Critical code guardrails, checked before delivery" in prompt
    assert "Treat narrative_guidance as code-generated logic guidance" in prompt
    assert "Do not use the phrases 'pricing in'" in prompt
    assert "DXY is up, so treat dollar pressure as tighter funding for EM debt." in prompt


def test_narrative_prompt_requires_contrarian_book_implication() -> None:
    prompt = build_narrative_prompt(build_sample_brief_data())

    assert "state why that view could be wrong" in prompt
    assert "tie the implication back to the assumed book" in prompt
    assert "Do not invent a further-reading link" in prompt


def test_topic_selection_can_rank_theme_radar_news_signal(tmp_path) -> None:
    portfolio_path = tmp_path / "positions.csv"
    portfolio_path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,quantity,unit,notes",
                "2026-06-01,Gold,overweight,medium,,,Inflation hedge",
            ]
        ),
        encoding="utf-8",
    )
    data = replace(
        build_sample_brief_data(),
        market_rows=[
            MarketRow("Gold", "$2,352", "$2,351", "+0.0%", "Gold is holding steady; rates and DXY will decide whether the overweight has cover."),
            MarketRow("US 10Y yield", "4.42%", "4.42%", "+0 bp", "Treasuries are not moving the story; watch dollar and commodity signals instead."),
            MarketRow("DXY", "104.8", "104.8", "+0.0%", "The dollar is not adding a fresh shock; pair-specific FX moves matter more today."),
        ],
        calendar=[],
        theme_radar=[
            ThemeItem(
                "Under one roof: housing and inflation expectations",
                "Bank Underground",
                "https://bankunderground.co.uk/example",
                "Housing costs may influence inflation expectations beyond ordinary consumer prices. The evidence links household inflation views to housing market dynamics and argues that this channel matters for monetary policy.",
                "What this means for our book: inflation and rate evidence can either protect or pressure the gold overweight.",
                "RSS excerpt",
            )
        ],
    )

    selected = select_portfolio_topics(data, run_date=date(2026, 6, 11), portfolio_path=portfolio_path)

    assert selected.topic_candidates[0]["origin"] == "theme"
    assert selected.three_thing_titles[0] == "Inflation Expectations Signal"


def test_topic_selection_can_rank_ai_theme_signal(tmp_path) -> None:
    portfolio_path = tmp_path / "positions.csv"
    portfolio_path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,significance,quantity,unit,notes",
                "2026-06-12,US AI semiconductors basket,overweight,medium,high,,,AI capex proxy",
            ]
        ),
        encoding="utf-8",
    )
    data = replace(
        build_sample_brief_data(),
        market_rows=[
            MarketRow("US AI semiconductors basket", "$315.00", "$314.80", "+0.1%", "Semiconductors are not moving the AI story today; watch rates, Nasdaq, and power proxies."),
            MarketRow("Nasdaq 100", "21,100", "21,090", "+0.0%", "Nasdaq is not adding a fresh signal; semiconductors and rates are the cleaner AI read-through."),
            MarketRow("S&P 500", "7,269", "7,266", "+0.0%", "US equities give little direction; rates and FX are the cleaner overnight signal."),
        ],
        calendar=[],
        theme_radar=[
            ThemeItem(
                "AI chip capex is moving from hype to delivery risk",
                "Reuters",
                "https://www.reuters.com/example-ai-chip-capex",
                "Artificial intelligence spending remains concentrated in semiconductors, GPUs, cloud capacity, and data center buildouts. The evidence is stronger capex guidance from hyperscalers, tight memory supply, and a bigger focus on whether chip demand can translate into earnings.",
                "What this means for our book: AI semiconductor exposure matters because a capex slowdown would hurt growth leadership even if broad equities look calm.",
                "search result snippet",
            )
        ],
    )

    selected = select_portfolio_topics(data, run_date=date(2026, 6, 12), portfolio_path=portfolio_path)

    assert selected.topic_candidates[0]["origin"] == "theme"
    assert selected.three_thing_titles[0] == "AI Semiconductor Cycle"
    assert selected.topic_candidates[0]["portfolio_asset"] == "US AI semiconductors basket"
    assert selected.topic_selection_report[0]["significance"] == "high"


def test_topic_selection_report_records_readable_reason(tmp_path) -> None:
    portfolio_path = tmp_path / "positions.csv"
    portfolio_path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,significance,quantity,unit,notes",
                "2026-06-12,US AI semiconductors basket,overweight,medium,high,,,AI capex proxy",
            ]
        ),
        encoding="utf-8",
    )
    data = replace(
        build_sample_brief_data(),
        market_rows=[
            MarketRow("US AI semiconductors basket", "$315.00", "$300.00", "+5.0%", "Semiconductor strength supports the AI capex theme and high-beta growth leadership."),
            MarketRow("Nasdaq 100", "21,100", "20,900", "+1.0%", "Growth leadership is firm, supporting AI-linked equity exposure if rates stay contained."),
            MarketRow("VIX", "14.0", "15.0", "-6.7%", "Lower volatility supports risk appetite, but it can also make hedges look underpriced."),
        ],
        calendar=[],
        theme_radar=[],
    )

    selected = select_portfolio_topics(data, run_date=date(2026, 6, 12), portfolio_path=portfolio_path)
    report = selected.topic_selection_report[0]

    assert report["title"] == "AI Semiconductor Cycle"
    assert "why_selected" in report
    assert "portfolio significance" in str(report["why_selected"])
    assert report["score_components"]["significance"] == 1.25


def test_topic_selection_applies_reader_feedback_adjustment(tmp_path) -> None:
    portfolio_path = tmp_path / "positions.csv"
    portfolio_path.write_text(
        "\n".join(
            [
                "effective_date,asset,position,exposure,quantity,unit,notes",
                "2026-06-01,Gold,overweight,medium,,,Inflation hedge",
            ]
        ),
        encoding="utf-8",
    )
    feedback_path = tmp_path / "daily_feedback.local.csv"
    feedback_path.write_text(
        "\n".join(
            [
                "date,section,item,usefulness,comment",
                "2026-06-10,Theme Radar,Under one roof,2,Too generic for today's book",
            ]
        ),
        encoding="utf-8",
    )
    data = replace(
        build_sample_brief_data(),
        market_rows=[
            MarketRow("Gold", "$2,352", "$2,351", "+0.0%", "Gold is holding steady; rates and DXY will decide whether the overweight has cover."),
            MarketRow("US 10Y yield", "4.42%", "4.42%", "+0 bp", "Treasuries are not moving the story; watch dollar and commodity signals instead."),
            MarketRow("DXY", "104.8", "104.8", "+0.0%", "The dollar is not adding a fresh shock; pair-specific FX moves matter more today."),
        ],
        calendar=[],
        theme_radar=[
            ThemeItem(
                "Under one roof: housing and inflation expectations",
                "Bank Underground",
                "https://bankunderground.co.uk/example",
                "Housing costs may influence inflation expectations beyond ordinary consumer prices. The evidence links household inflation views to housing market dynamics and argues that this channel matters for monetary policy.",
                "What this means for our book: inflation and rate evidence can either protect or pressure the gold overweight.",
                "RSS excerpt",
            )
        ],
    )

    selected = select_portfolio_topics(
        data,
        run_date=date(2026, 6, 11),
        portfolio_path=portfolio_path,
        feedback_path=feedback_path,
    )

    assert selected.topic_candidates[0]["score_components"]["reader_feedback"] < 0
    assert "reader_feedback" in selected.data_sources


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


def test_parse_narrative_response_rejects_ecb_hawkish_euro_negative_error() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "The ECB meeting is the main European event risk. A hawkish ECB surprise could pressure EUR/USD into the close. So what: keep FX exposure hedged.",
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
        assert "hawkish ECB" in str(exc)
    else:
        raise AssertionError("Expected ECB hawkish euro-negative validation to fail")


def test_parse_narrative_response_rejects_ecb_dovish_euro_positive_error() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "The ECB meeting is the main European event risk. A dovish ECB surprise could lead to broad euro strength into the close. So what: keep FX exposure hedged.",
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
        assert "dovish ECB" in str(exc)
    else:
        raise AssertionError("Expected ECB dovish euro-positive validation to fail")


def test_parse_narrative_response_rejects_dollar_support_pressure_on_long_usdjpy() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "A hot US inflation print would likely support the dollar. So what: this could add pressure to our long USD/JPY position.",
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
        assert "dollar support" in str(exc)
    else:
        raise AssertionError("Expected dollar-support pressure validation to fail")


def test_parse_narrative_response_rejects_hawkish_fed_pressure_on_long_usdjpy() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "Elevated inflation prints could pressure the long USD/JPY position by reinforcing hawkish Fed expectations. So what: keep FX exposure hedged.",
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
        assert "hawkish US rates" in str(exc)
    else:
        raise AssertionError("Expected hawkish-Fed pressure validation to fail")


def test_parse_narrative_response_rejects_hotter_inflation_lower_yields() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "A hotter-than-expected US inflation print would likely pressure US 10Y yields lower. So what: keep rates exposure hedged.",
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
        assert "hotter inflation" in str(exc)
    else:
        raise AssertionError("Expected hotter-inflation direction validation to fail")


def test_parse_narrative_response_rejects_cooler_inflation_higher_yields() -> None:
    base = build_sample_brief_data()
    response = """
    {
      "three_things": [
        "A cooler-than-expected US inflation print would likely send Treasury yields higher. So what: keep rates exposure hedged.",
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
        assert "cooler inflation" in str(exc)
    else:
        raise AssertionError("Expected cooler-inflation direction validation to fail")


def test_parse_narrative_response_rejects_us_yield_direction_mismatch() -> None:
    base = build_sample_brief_data()
    adjusted_rows = [
        replace(row, change="-2 bp") if row.asset == "US 10Y yield" else row
        for row in base.market_rows
    ]
    base = replace(base, market_rows=adjusted_rows)
    response = """
    {
      "three_things": [
        "Rising US yields are pressuring EUR/USD lower and supporting USD/JPY. So what: keep the rates-sensitive book on alert.",
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
        assert "US yields rose" in str(exc)
    else:
        raise AssertionError("Expected US yield direction validation to fail")


def test_parse_narrative_response_rejects_oil_up_inflation_easing() -> None:
    base = build_sample_brief_data()

    _assert_first_thing_rejected(
        base,
        "WTI oil rose 1.7%, but oil eased inflation pressure across the book. So what: EM debt exposure should be treated as safer.",
        "oil_inflation_direction",
    )


def test_parse_narrative_response_rejects_oil_down_inflation_pressure() -> None:
    base = build_sample_brief_data()
    adjusted_rows = [
        replace(row, close="$75.80", prior="$77.10", change="-1.7%") if row.asset == "WTI oil" else row
        for row in base.market_rows
    ]
    base = replace(base, market_rows=adjusted_rows)

    _assert_first_thing_rejected(
        base,
        "WTI oil fell 1.7%, adding inflation pressure to the morning tape. So what: EM debt exposure should stay defensive.",
        "oil_inflation_direction",
    )


def test_parse_narrative_response_rejects_gold_up_overweight_hurt() -> None:
    base = build_sample_brief_data()
    adjusted_rows = [
        replace(row, close="$2,390", prior="$2,371", change="+0.8%") if row.asset == "Gold" else row
        for row in base.market_rows
    ]
    base = replace(base, market_rows=adjusted_rows)

    _assert_first_thing_rejected(
        base,
        "Gold rose 0.8%, but this hurts the gold overweight. So what: reduce confidence in the inflation hedge.",
        "gold_position_direction",
    )


def test_parse_narrative_response_rejects_gold_down_overweight_helped() -> None:
    base = build_sample_brief_data()

    _assert_first_thing_rejected(
        base,
        "Gold fell 0.8%, which helps the gold overweight. So what: keep the inflation hedge as the cleaner expression.",
        "gold_position_direction",
    )


def test_parse_narrative_response_rejects_spx_up_underweight_tailwind() -> None:
    base = build_sample_brief_data()

    _assert_first_thing_rejected(
        base,
        "S&P 500 rose 0.4%, which is a tailwind for our underweight S&P 500 position. So what: keep the equity underweight unchanged.",
        "equity_underweight_direction",
    )


def test_parse_narrative_response_allows_spx_up_but_underweight_hurt() -> None:
    base = build_sample_brief_data()

    generated = parse_narrative_response(
        _valid_response_with_first_thing(
            "S&P 500 rose 0.4%, which hurts the underweight S&P 500 position but supports broad risk appetite. So what: keep the underweight under review."
        ),
        base,
    )

    assert "hurts the underweight" in generated.three_things[0]


def test_parse_narrative_response_rejects_dxy_up_dollar_pressure_eased() -> None:
    base = build_sample_brief_data()

    _assert_first_thing_rejected(
        base,
        "DXY rose 0.5%, but dollar pressure eased for the book. So what: EM debt exposure should get relief.",
        "dollar_direction",
    )


def test_parse_narrative_response_rejects_dxy_down_dollar_pressure_tightened() -> None:
    base = build_sample_brief_data()
    adjusted_rows = [
        replace(row, close="103.8", prior="104.3", change="-0.5%") if row.asset == "DXY" else row
        for row in base.market_rows
    ]
    base = replace(base, market_rows=adjusted_rows)

    _assert_first_thing_rejected(
        base,
        "DXY fell 0.5%, but dollar funding pressure tightened. So what: EM debt exposure should stay defensive.",
        "dollar_direction",
    )


def test_parse_narrative_response_allows_dxy_up_with_yield_pressure_relief() -> None:
    base = build_sample_brief_data()
    adjusted_rows = [
        replace(row, change="-2 bp") if row.asset == "US 10Y yield" else row
        for row in base.market_rows
    ]
    base = replace(base, market_rows=adjusted_rows)

    generated = parse_narrative_response(
        _valid_response_with_first_thing(
            "DXY rose 0.5%, while lower US yields eased duration pressure. So what: EM debt still faces dollar headwinds, but rate relief helps the duration leg."
        ),
        base,
    )

    assert "rate relief" in generated.three_things[0]


def test_parse_narrative_response_rejects_vix_up_hedging_faded() -> None:
    base = build_sample_brief_data()
    base = replace(
        base,
        market_rows=[
            *base.market_rows,
            MarketRow("VIX", "18.72", "18.00", "+4.0%", "Higher volatility signals defensive hedging demand and weaker risk appetite."),
        ],
    )

    _assert_first_thing_rejected(
        base,
        "VIX rose 4.0%, but hedging demand faded across risk assets. So what: risk exposure can be treated more calmly.",
        "volatility_direction",
    )


def test_parse_narrative_response_rejects_vix_down_defensive_stress() -> None:
    base = build_sample_brief_data()
    base = replace(
        base,
        market_rows=[
            *base.market_rows,
            MarketRow("VIX", "17.28", "18.00", "-4.0%", "Lower volatility supports risk appetite, but it can also make hedges look underpriced."),
        ],
    )

    _assert_first_thing_rejected(
        base,
        "VIX fell 4.0%, but volatility stress increased across the book. So what: keep risk exposure defensive.",
        "volatility_direction",
    )


def test_parse_narrative_response_allows_vix_down_defensive_hedge_context() -> None:
    base = build_sample_brief_data()
    base = replace(
        base,
        market_rows=[
            *base.market_rows,
            MarketRow("VIX", "17.28", "18.00", "-4.0%", "Lower volatility supports risk appetite, but it can also make hedges look underpriced."),
        ],
    )

    generated = parse_narrative_response(
        _valid_response_with_first_thing(
            "VIX fell 4.0%, so volatility stress eased and defensive hedges look less urgent. So what: equity beta has support, but cheap hedges can still be useful."
        ),
        base,
    )

    assert "defensive hedges" in generated.three_things[0]


def test_parse_narrative_response_rejects_em_debt_helped_by_yields_or_dollar() -> None:
    base = build_sample_brief_data()

    _assert_first_thing_rejected(
        base,
        "EM debt exposure is helped by higher US yields and stronger dollar funding pressure. So what: add duration risk.",
        "em_debt_macro_direction",
    )


def test_parse_narrative_response_allows_em_debt_supported_by_equities_despite_dollar() -> None:
    base = build_sample_brief_data()

    generated = parse_narrative_response(
        _valid_response_with_first_thing(
            "EM debt faces mixed signals. Equities provide partial support for EM beta, but dollar strength remains a funding headwind. So what: keep EM exposure selective."
        ),
        base,
    )

    assert "funding headwind" in generated.three_things[0]


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


def test_parse_narrative_response_rewrites_theme_explores_openers() -> None:
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

    generated = parse_narrative_response(response, base)

    assert generated.theme_radar[0].summary.startswith("The analysis shows")


def test_parse_narrative_response_rewrites_theme_examines_openers() -> None:
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
          "summary": "This analysis examines how fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. The point is not that growth is suddenly stronger, but that investors want more compensation for duration risk when supply headlines keep returning. The note says duration risk remains central.",
          "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring."
        }
      ],
      "contrarian_corner": "The simple read is that USD/JPY can keep rising while US yields stay high and the dollar is firm. A trigger that would challenge this view is a direct warning from Japanese officials that forces investors to reassess yen-reversal risk and reduce exposure before the next policy headline."
    }
    """

    generated = parse_narrative_response(response, base)

    assert generated.theme_radar[0].summary.startswith("The analysis shows")


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
          "summary": "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. The evidence is auction tails, dealer balance-sheet limits, and resilient breakevens. The point is not that growth is suddenly stronger, but that investors want more compensation for duration risk when supply headlines keep returning. The note adds that duration risk remains central when supply pressure keeps returning. The selector picked it because the feed discusses rates and credit. Portfolio link: use it as source input for judging whether the assumed book needs attention today. So what: USD/JPY can keep support, but gold needs close monitoring.",
          "book_impact": "What this means for our book: USD/JPY can keep support, but gold needs close monitoring."
        }
      ],
      "contrarian_corner": "The simple read is that USD/JPY can keep rising while US yields stay high and the dollar is firm. A trigger that would challenge this view is a direct warning from Japanese officials that forces investors to reassess yen-reversal risk and reduce exposure before the next policy headline."
    }
    """

    generated = parse_narrative_response(response, base)

    assert "So what:" not in generated.theme_radar[0].summary
    assert "selector picked" not in generated.theme_radar[0].summary.lower()
    assert "portfolio link" not in generated.theme_radar[0].summary.lower()
    assert "source input" not in generated.theme_radar[0].summary.lower()
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
        theme_history_path=tmp_path / "theme_history.json",
        theme_recent_days=7,
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
    markdown = result.output_paths["latest_markdown"].read_text(encoding="utf-8")
    assert "Updated as of:" in markdown
    log_event = json.loads(result.log_path.read_text(encoding="utf-8"))
    assert log_event["run_mode"] == "sample"
    assert log_event["quality_report"]["verdict"] == "passed"
    assert result.quality_report["send_allowed"] is True


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
        theme_history_path=tmp_path / "theme_history.json",
        theme_recent_days=7,
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
    assert "topic_selection" in log_event
    assert "selected_topics" in log_event["topic_selection"]
    assert "selected_chart" in log_event["topic_selection"]
    assert log_event["quality_report"]["verdict"] == "passed"
    assert log_event["quality_report"]["send_allowed"] is True


def test_repaired_llm_validation_warning_is_logged(tmp_path, monkeypatch) -> None:
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
        theme_history_path=tmp_path / "theme_history.json",
        theme_recent_days=7,
        portfolio_path=tmp_path / "positions.csv",
        output_dir=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
    )

    def fake_synthesize(_settings, data):
        return SynthesisResult(
            data=replace(data, data_sources=[*data.data_sources, "gemini_synthesis"]),
            token_usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, provider="gemini"),
            estimated_cost_usd=0.00003,
            provider="gemini",
            model="gemini-2.5-flash-lite",
            prompt_version="test_prompt",
            validation_attempts=2,
            validation_repair_count=1,
            validation_errors=("three_things item 1 inverted US yield direction",),
        )

    monkeypatch.setattr(runner_module, "synthesize_with_gemini", fake_synthesize)

    result = run_brief(settings, send=False, use_llm=True)
    log_event = json.loads(result.log_path.read_text(encoding="utf-8"))

    assert log_event["quality_report"]["verdict"] == "warning"
    assert log_event["quality_report"]["send_allowed"] is True
    assert log_event["quality_report"]["narrative_validation_errors"] == [
        "three_things item 1 inverted US yield direction"
    ]


def test_llm_validation_failure_blocks_send_and_writes_quality_log(tmp_path, monkeypatch) -> None:
    settings = Settings(
        llm_provider="gemini",
        gemini_api_key="test-key",
        gemini_model="gemini-2.5-flash-lite",
        deepseek_api_key=None,
        deepseek_model="deepseek-v4-flash",
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_user="sender@example.com",
        smtp_password="app-password",
        brief_from_email="sender@example.com",
        brief_to_email="reader@example.com",
        timezone="Asia/Shanghai",
        run_mode="sample",
        market_data_mode="sample",
        calendar_mode="sample",
        theme_source_mode="sample",
        theme_history_path=tmp_path / "theme_history.json",
        theme_recent_days=7,
        portfolio_path=tmp_path / "positions.csv",
        output_dir=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
    )

    def fake_synthesize(_settings, _data):
        raise RuntimeError("Gemini response failed validation after retries: bad macro logic")

    def fake_send_email(*_args, **_kwargs):
        raise AssertionError("send_email must not be called after narrative validation failure")

    monkeypatch.setattr(runner_module, "synthesize_with_gemini", fake_synthesize)
    monkeypatch.setattr(runner_module, "send_email", fake_send_email)

    try:
        run_brief(settings, send=True, use_llm=True, llm_failure_mode="block")
    except RuntimeError as exc:
        assert "Quality gate blocked run before delivery" in str(exc)
    else:
        raise AssertionError("Expected LLM validation failure to block the run")

    logs = list((tmp_path / "logs").glob("run-*.jsonl"))
    assert len(logs) == 1
    log_event = json.loads(logs[0].read_text(encoding="utf-8"))
    assert log_event["delivery_status"] == "blocked_quality_gate"
    assert log_event["delivery_attempted"] is False
    assert log_event["quality_report"]["verdict"] == "failed"
    assert log_event["quality_report"]["send_allowed"] is False


def test_llm_validation_failure_can_write_data_only_fallback(tmp_path, monkeypatch) -> None:
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
        theme_history_path=tmp_path / "theme_history.json",
        theme_recent_days=7,
        portfolio_path=tmp_path / "positions.csv",
        output_dir=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
    )

    def fake_synthesize(_settings, _data):
        raise RuntimeError("Gemini response failed validation after retries: bad macro logic")

    monkeypatch.setattr(runner_module, "synthesize_with_gemini", fake_synthesize)

    result = run_brief(settings, send=False, use_llm=True, llm_failure_mode="data_only")
    log_event = json.loads(result.log_path.read_text(encoding="utf-8"))
    markdown = result.output_paths["latest_markdown"].read_text(encoding="utf-8")

    assert result.delivery_status == "dry_run_data_only"
    assert log_event["llm_status"] == "data_only_fallback"
    assert log_event["quality_report"]["verdict"] == "warning"
    assert log_event["quality_report"]["send_allowed"] is True
    assert log_event["quality_report"]["llm_fallback_used"] is True
    assert "Data-only fallback" in markdown
    assert "data_only_llm_failure_fallback" in log_event["data_sources"]


def test_section_fallback_salvages_valid_sections_and_withholds_failed_section() -> None:
    base = build_sample_brief_data()
    response = json.dumps(
        {
            "three_things": [
                {
                    "body": "US yields and the dollar are doing the work, while gold is softer against the rate move.",
                    "so_what": "keep the FX and gold legs under review without inventing a new trade signal.",
                },
                {
                    "body": "Oil is firmer, which keeps inflation risk alive even if broader risk appetite is mixed.",
                    "so_what": "treat EM duration exposure cautiously until energy pressure fades.",
                },
                {
                    "body": "Equities and BTC are useful cross-checks, but the dashboard reads more like a rates morning.",
                    "so_what": "do not over-read one risk-asset bounce as a clean reflation signal.",
                },
            ],
            "theme_radar": [
                {
                    "title": "Unverified new theme",
                    "source": "Unknown source",
                    "link": "https://example.com/unknown",
                    "summary": (
                        "This candidate does not reuse an existing Theme Radar source, so the section should be "
                        "withheld by the section fallback even though other sections can pass. The text is long "
                        "enough to avoid word-count failure, but the source identity is not allowed."
                    ),
                    "book_impact": "What this means for our book: this should not be accepted.",
                }
            ],
            "contrarian_corner": (
                "The simple read is that higher yields and a firmer dollar keep pressure on gold and EM debt while "
                "supporting USD/JPY. That could be wrong if incoming inflation and growth data soften together, "
                "letting yields fall without hurting risk appetite. The trigger would be a softer US inflation print "
                "paired with stable oil, which would reduce pressure on the assumed book."
            ),
        }
    )

    result = build_section_fallback_narrative(response, base, "theme failed validation")

    assert result.fallback_sections == ("theme_radar",)
    assert result.data.three_things[0].startswith("US yields and the dollar")
    assert result.data.theme_radar[0].summary.startswith("Narrative summary withheld after validation")
    assert "gemini_section_fallback" in result.data.data_sources


def test_llm_validation_failure_can_write_section_fallback(tmp_path, monkeypatch) -> None:
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
        theme_history_path=tmp_path / "theme_history.json",
        theme_recent_days=7,
        portfolio_path=tmp_path / "positions.csv",
        output_dir=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
    )

    def fake_synthesize(_settings, _data):
        raise RuntimeError("Gemini response failed validation after retries: bad macro logic")

    monkeypatch.setattr(runner_module, "synthesize_with_gemini", fake_synthesize)

    result = run_brief(settings, send=False, use_llm=True, llm_failure_mode="section_fallback")
    log_event = json.loads(result.log_path.read_text(encoding="utf-8"))
    markdown = result.output_paths["latest_markdown"].read_text(encoding="utf-8")

    assert result.delivery_status == "dry_run_section_fallback"
    assert log_event["llm_status"] == "section_fallback"
    assert log_event["quality_report"]["verdict"] == "warning"
    assert log_event["quality_report"]["send_allowed"] is True
    assert log_event["quality_report"]["llm_fallback_used"] is True
    assert log_event["quality_report"]["llm_fallback_sections"] == [
        "three_things",
        "theme_radar",
        "contrarian_corner",
    ]
    assert "Contrarian Corner is withheld" in markdown
    assert "gemini_section_fallback" in log_event["data_sources"]


def test_compare_gemini_models_logs_each_model_result(tmp_path, monkeypatch) -> None:
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
        timezone="Asia/Hong_Kong",
        run_mode="sample",
        market_data_mode="sample",
        calendar_mode="sample",
        theme_source_mode="sample",
        theme_history_path=tmp_path / "theme_history.json",
        theme_recent_days=7,
        portfolio_path=tmp_path / "positions.csv",
        output_dir=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
    )

    def fake_synthesize(model_settings, data):
        if model_settings.gemini_model == "gemini-2.5-pro":
            return SynthesisResult(
                data=data,
                token_usage=TokenUsage(input_tokens=200, output_tokens=80, total_tokens=280, provider="gemini"),
                estimated_cost_usd=0.001,
                provider="gemini",
                model=model_settings.gemini_model,
                prompt_version="test_prompt",
                validation_attempts=2,
                validation_repair_count=1,
                validation_errors=("repair needed",),
            )
        return SynthesisResult(
            data=data,
            token_usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, provider="gemini"),
            estimated_cost_usd=0.00003,
            provider="gemini",
            model=model_settings.gemini_model,
            prompt_version="test_prompt",
        )

    monkeypatch.setattr(model_compare_module, "synthesize_with_gemini", fake_synthesize)

    results, log_path = compare_gemini_models(
        settings,
        models=["gemini-2.5-flash-lite", "gemini-2.5-pro"],
        run_date=date(2026, 6, 11),
    )

    assert [result.model for result in results] == ["gemini-2.5-flash-lite", "gemini-2.5-pro"]
    assert [result.status for result in results] == ["passed", "warning"]
    assert results[1].validation_repair_count == 1
    log_event = json.loads(log_path.read_text(encoding="utf-8"))
    assert log_event["models"] == ["gemini-2.5-flash-lite", "gemini-2.5-pro"]
    assert "Cost is estimated only" in log_event["cost_estimate_note"]
    assert log_event["results"][0]["total_tokens"] == 150
    assert log_event["results"][1]["validation_repair_count"] == 1
    assert log_event["results"][1]["validation_errors"] == ["repair needed"]


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
                "^NDX": [500.0, 510.0],
                "SOXX": [250.0, 260.0],
                "XLU": [70.0, 71.0],
                "^STOXX50E": [200.0, 198.0],
                "^TNX": [4.40, 4.45],
                "KWEB": [30.0, 30.3],
                "GC=F": [2300.0, 2310.0],
                "BZ=F": [84.0, 83.0],
                "CL=F": [80.0, 82.0],
                "HG=F": [4.30, 4.40],
                "^VIX": [16.0, 15.0],
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
            return FakeResponse(
                {
                    "rates": {
                        "2026-03-06": {"JPY": 150.0},
                        "2026-03-20": {"JPY": 151.5},
                        "2026-04-03": {"JPY": 152.0},
                        "2026-04-17": {"JPY": 153.4},
                        "2026-05-01": {"JPY": 154.2},
                        "2026-05-15": {"JPY": 155.0},
                        "2026-05-29": {"JPY": 157.4},
                        "2026-06-04": {"JPY": 158.0},
                        "2026-06-05": {"JPY": 159.0},
                    }
                }
            )
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
    assert row_by_asset["Nasdaq 100"].close == "510.00"
    assert row_by_asset["US AI semiconductors basket"].close == "$260.00"
    assert row_by_asset["US data-center power basket"].close == "$71.00"
    assert row_by_asset["Copper"].close == "$4.40"
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
    assert len(result.data.chart_series) > 5
    assert result.data.chart_series[-1] == ("2026-06-05", 159.0)
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
    assert "yahoo_chart:^NDX" in result.sources
    assert "yahoo_chart:SOXX" in result.sources
    assert "yahoo_chart:XLU" in result.sources
    assert "yahoo_chart:HG=F" in result.sources
    assert result.cached_assets == []
    assert any("extracted at" in note for note in result.data.dashboard_notes)
    assert any("Additional information about timing" in note for note in result.data.dashboard_notes)
    assert any("[Japan MOF JGB yield CSV]" in note for note in result.data.dashboard_notes)
    assert any("US AI semiconductors" in note for note in result.data.dashboard_notes)
    assert any("rates (US/Japan 10Y)" in note for note in result.data.dashboard_notes)
    rendered = render_markdown(result.data)
    assert "Frankfurter FX rows use the latest published daily reference rate" in rendered
    assert "Source Status shows live, cached, or scaffold fallback rows" not in rendered
    assert "value cells are left blank" in rendered
    assert "[Yahoo Finance quote pages](https://finance.yahoo.com/quote/%5ETNX/)" in rendered
    assert "[Frankfurter](https://frankfurter.dev/)" in rendered


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
    assert "| S&P 500 † | 102.00 |" in render_markdown(second.data)


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
                    "title": "Core CPI m/m",
                    "country": "USD",
                    "date": "2026-06-10T08:30:00-04:00",
                    "impact": "High",
                    "forecast": "0.5%",
                    "previous": "0.4%",
                },
                {
                    "title": "CPI y/y",
                    "country": "USD",
                    "date": "2026-06-10T08:30:00-04:00",
                    "impact": "High",
                    "forecast": "2.9%",
                    "previous": "2.8%",
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

    assert len(result.data.calendar) == 4
    assert event_by_name["USD Non-Farm Employment Change"].session == "US"
    assert event_by_name["USD Non-Farm Employment Change"].consensus == "85K"
    assert event_by_name["USD Non-Farm Employment Change"].event_date == "2026-06-06"
    assert event_by_name["USD Non-Farm Employment Change"].status == "Live"
    assert event_by_name["USD Non-Farm Employment Change"].link == "https://www.forexfactory.com/calendar?day=jun6.2026"
    assert event_by_name["EUR Core CPI Flash Estimate y/y"].session == "Europe"
    assert event_by_name["EUR Core CPI Flash Estimate y/y"].status == "Live"
    assert event_by_name["CNY RatingDog Manufacturing PMI"].session == "Asia"
    assert event_by_name["CNY RatingDog Manufacturing PMI"].event_date == "2026-06-07"
    assert event_by_name["CNY RatingDog Manufacturing PMI"].status == "*"
    assert "USD Core CPI m/m" in event_by_name
    assert "USD CPI y/y" not in event_by_name
    assert "NZD Bank Holiday" not in event_by_name
    assert result.fallback_events == []
    assert "faireconomy:ff_calendar_thisweek" in result.sources
    assert "[USD Non-Farm Employment Change](https://www.forexfactory.com/calendar?day=jun6.2026)" in render_markdown(result.data)
    assert "Calendar status notes:" in render_markdown(result.data)
    assert "Live = event is dated today in the calendar source." in render_markdown(result.data)
    assert "* = next-session or nearest source-week item" in render_markdown(result.data)
    assert "† = cached real calendar row after live refresh failed" not in render_markdown(result.data)
    assert "[Forex Factory/Fair Economy weekly feed](https://www.forexfactory.com/calendar)" in render_markdown(result.data)


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
    assert "† = cached real calendar row after live refresh failed" in render_markdown(result.data)


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
        theme_history_path=tmp_path / "theme_history.json",
        theme_recent_days=7,
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

    assert log_event["run_mode"] == "live_calendar"
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

THEME_FEED_THREE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Under one roof: housing and inflation expectations</title>
      <link>https://bankunderground.co.uk/example/housing-inflation/</link>
      <pubDate>Fri, 05 Jun 2026 10:00:00 +0000</pubDate>
      <description><![CDATA[
        The post argues that housing costs and inflation expectations can interact through household
        balance sheets, wage bargaining, and central-bank credibility. It links sticky shelter costs,
        price stability, and interest rate expectations in a way that matters for gold and duration risk.
      ]]></description>
    </item>
  </channel>
</rss>
"""

GOOGLE_NEWS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Japan officials warn on yen volatility as USD/JPY rises</title>
      <link>https://news.google.com/rss/articles/example-yen-warning</link>
      <pubDate>Fri, 05 Jun 2026 09:00:00 +0000</pubDate>
      <source url="https://www.reuters.com">Reuters</source>
      <description><![CDATA[
        Japanese officials warned that they are watching exchange rate volatility as the yen weakens
        against the dollar. The article discusses intervention risk, the finance ministry, Bank of Japan
        policy expectations, and the pressure created by a stronger dollar.
      ]]></description>
    </item>
  </channel>
</rss>
"""

THEME_FEED_SIMILAR_YEN = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Japan finance ministry warns again on yen volatility</title>
      <link>https://example.com/yen-warning-new</link>
      <pubDate>Fri, 05 Jun 2026 12:00:00 +0000</pubDate>
      <description><![CDATA[
        Japanese officials warned that they are monitoring exchange rate volatility as the yen weakens
        against the dollar. The article discusses intervention risk, the finance ministry, Bank of Japan
        policy expectations, and pressure from a stronger dollar.
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
        if "source-three" in url:
            return FakeResponse(text=THEME_FEED_THREE)
        if "news.google.com" in url:
            return FakeResponse(text=GOOGLE_NEWS_FEED)
        raise RuntimeError("unexpected feed")


class FailingThemeClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url):
        raise RuntimeError(f"simulated feed outage: {url}")


class SimilarThemeClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url):
        if "similar-yen" in url:
            return FakeResponse(text=THEME_FEED_SIMILAR_YEN)
        if "source-one" in url:
            return FakeResponse(text=THEME_FEED_ONE)
        if "source-two" in url:
            return FakeResponse(text=THEME_FEED_TWO)
        raise RuntimeError("unexpected feed")


def _theme_sources() -> list[ThemeSource]:
    return [
        ThemeSource("FRED Blog", "https://source-one.test/feed/", "theme_feed:test_fred"),
        ThemeSource("Liberty Street Economics", "https://source-two.test/feed/", "theme_feed:test_liberty"),
    ]


def _theme_sources_with_third() -> list[ThemeSource]:
    return [
        *_theme_sources(),
        ThemeSource("Bank Underground", "https://source-three.test/feed/", "theme_feed:test_bank"),
    ]


def test_theme_feed_parser_uses_richer_content_field_when_available() -> None:
    feed = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
      <channel>
        <item>
          <title>Gold investors watch Treasury yields and inflation expectations</title>
          <link>https://example.com/gold-yields</link>
          <pubDate>Thu, 04 Jun 2026 13:00:00 +0000</pubDate>
          <description>Short gold note.</description>
          <content:encoded><![CDATA[
            Gold investors are watching Treasury yields, inflation expectations, and the dollar because
            each can change the opportunity cost of holding the metal. The longer feed content explains
            how rate-sensitive gold positions react when nominal yields rise but inflation expectations
            remain sticky, and why this matters for portfolio hedges.
          ]]></content:encoded>
        </item>
      </channel>
    </rss>
    """

    candidates = parse_feed(feed, ThemeSource("Bank Underground", "https://example.com/feed", "theme_feed:test"))

    assert len(candidates) == 1
    assert candidates[0].source_depth == "RSS content field"
    assert "longer feed content" in candidates[0].text


def test_article_text_extractor_reads_article_paragraphs_and_ignores_boilerplate() -> None:
    html = f"""
    <html>
      <body>
        <nav>{_words("navcookie", 140)}</nav>
        <script>{_words("scriptnoise", 140)}</script>
        <article>
          <p>{_words("inflation", 70)}</p>
          <p>{_words("duration", 70)}</p>
        </article>
        <footer>{_words("footernoise", 140)}</footer>
      </body>
    </html>
    """

    extracted = _extract_article_text(html)

    assert "inflation0" in extracted
    assert "duration0" in extracted
    assert "navcookie0" not in extracted
    assert "scriptnoise0" not in extracted
    assert "footernoise0" not in extracted


def test_article_text_extractor_rejects_short_pages() -> None:
    html = "<html><body><article><p>Short inflation and rates note.</p></article></body></html>"

    assert _extract_article_text(html) == ""


def test_article_text_extractor_rejects_publisher_navigation_paragraphs() -> None:
    html = f"""
    <html>
      <body>
        <article>
          <p>Look for our next post on June 22. « Previous item | Main | Next item » {_words("nav", 130)}</p>
          <p>{_words("credit", 70)}</p>
          <p>{_words("borrower", 70)}</p>
        </article>
      </body>
    </html>
    """

    extracted = _extract_article_text(html)

    assert "Look for our next post" not in extracted
    assert "Previous item" not in extracted
    assert "credit0" in extracted
    assert "borrower0" in extracted


def test_article_text_extractor_strips_leading_byline() -> None:
    html = f"""
    <html>
      <body>
        <article>
          <p>Rajashri Chakrabarti, Gabriel Leonard, Donald P. Morgan, Thu Pham, and Lee Seltzer In imperial China, {_words("credit", 130)}</p>
        </article>
      </body>
    </html>
    """

    extracted = _extract_article_text(html)

    assert extracted.startswith("In imperial China")
    assert "Rajashri Chakrabarti" not in extracted


def test_article_text_extractor_caps_long_pages() -> None:
    html = f"<html><body><article><p>{_words('macro', 520)}</p></article></body></html>"

    extracted = _extract_article_text(html)

    assert 440 <= _word_count(extracted) <= 450
    assert extracted.endswith(".")


def test_live_theme_radar_labels_article_text_when_available() -> None:
    article_html = f"""
    <html>
      <head>
        <meta property="article:published_time" content="2026-06-04T14:30:00Z">
      </head>
      <body>
        <article>
          <p>{_words("articlebodyinflation", 70)}</p>
          <p>{_words("articlebodyduration", 70)}</p>
        </article>
      </body>
    </html>
    """

    class ArticleTextThemeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url, **kwargs):
            if "source-one" in url:
                return FakeResponse(text=THEME_FEED_ONE)
            if "fredblog.stlouisfed.org/example/core-pce" in url:
                return FakeResponse(text=article_html)
            raise RuntimeError("unexpected URL")

    result = replace_theme_radar_with_live(
        build_sample_brief_data(),
        client_factory=ArticleTextThemeClient,
        sources=[ThemeSource("FRED Blog", "https://source-one.test/feed/", "theme_feed:test_fred")],
    )

    item = result.data.theme_radar[0]
    assert item.source_depth == "RSS excerpt + article text excerpt"
    assert "articlebodyinflation0" in item.summary


def test_live_theme_radar_article_fetch_limit_zero_disables_article_fetch() -> None:
    class UnexpectedArticleFetchClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url, **kwargs):
            if "source-one" in url:
                return FakeResponse(text=THEME_FEED_ONE)
            raise AssertionError("article page should not be fetched when article_fetch_limit=0")

    result = replace_theme_radar_with_live(
        build_sample_brief_data(),
        client_factory=UnexpectedArticleFetchClient,
        sources=[ThemeSource("FRED Blog", "https://source-one.test/feed/", "theme_feed:test_fred")],
        article_fetch_limit=0,
    )

    assert result.data.theme_radar[0].source_depth == "RSS excerpt"


def test_live_theme_radar_labels_article_metadata_when_available() -> None:
    article_html = """
    <html>
      <head>
        <meta property="og:title" content="Core inflation and rate expectations stay linked">
        <meta property="og:description" content="The metadata summary says core inflation, Treasury yields, and central-bank credibility remain connected because investors are still deciding whether price pressure is durable enough to keep policy rates restrictive.">
        <meta property="article:published_time" content="2026-06-04T14:30:00Z">
      </head>
      <body>Publisher page body is not used by this metadata-only enrichment test.</body>
    </html>
    """

    class MetadataThemeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url, **kwargs):
            if "source-one" in url:
                return FakeResponse(text=THEME_FEED_ONE)
            if "fredblog.stlouisfed.org/example/core-pce" in url:
                return FakeResponse(text=article_html)
            raise RuntimeError("unexpected URL")

    result = replace_theme_radar_with_live(
        build_sample_brief_data(),
        client_factory=MetadataThemeClient,
        sources=[ThemeSource("FRED Blog", "https://source-one.test/feed/", "theme_feed:test_fred")],
    )

    assert result.data.theme_radar[0].source_depth == "RSS excerpt + article metadata"


def test_live_theme_radar_keeps_rss_label_when_article_fetch_fails() -> None:
    class ArticleFetchFailureClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url, **kwargs):
            if "source-one" in url:
                return FakeResponse(text=THEME_FEED_ONE)
            if "fredblog.stlouisfed.org/example/core-pce" in url:
                raise RuntimeError("simulated article-page failure")
            raise RuntimeError("unexpected URL")

    result = replace_theme_radar_with_live(
        build_sample_brief_data(),
        client_factory=ArticleFetchFailureClient,
        sources=[ThemeSource("FRED Blog", "https://source-one.test/feed/", "theme_feed:test_fred")],
    )

    assert result.data.theme_radar[0].source_depth == "RSS excerpt"


def test_theme_source_score_prefers_article_text_over_metadata_and_snippets() -> None:
    article_item = ThemeItem(
        "Inflation pressure and duration risk",
        "FRED Blog",
        "https://example.com/article",
        "summary",
        "What this means for our book: watch rates.",
        "RSS excerpt + article text excerpt",
    )
    metadata_item = replace(article_item, source_depth="RSS excerpt + article metadata")
    snippet_item = replace(article_item, source="Reuters via Google News", source_depth="search result snippet")

    assert _theme_source_score(article_item) > _theme_source_score(metadata_item)
    assert _theme_source_score(metadata_item) > _theme_source_score(snippet_item)


def test_theme_radar_recent_topic_penalty_is_not_a_hard_restriction() -> None:
    repeat_rule = THEME_RULES[2]
    fresh_rule = THEME_RULES[3]
    repeat_candidate = ThemeCandidate(
        title="Japan officials warn on yen volatility as USD/JPY rises again",
        source="Reuters via Google News",
        link="https://example.com/repeated-yen-warning",
        text="Japan officials warn again on yen volatility, USD/JPY intervention risk, the Bank of Japan, and dollar pressure.",
        published_at=datetime(2026, 6, 10, 12, 0),
        matched_rule=repeat_rule,
        matched_keywords=("japan", "dollar", "yen"),
        score=20,
        source_depth="search result snippet",
        source_id="theme_search:test_usdjpy",
    )
    fresh_candidate = ThemeCandidate(
        title="Gold investors watch inflation and rate expectations",
        source="Bank Underground",
        link="https://example.com/fresh-gold-rates",
        text="Gold investors watch inflation and rate expectations as central banks assess price stability.",
        published_at=datetime(2026, 6, 10, 13, 0),
        matched_rule=fresh_rule,
        matched_keywords=("gold", "inflation", "rate"),
        score=5,
        source_depth="RSS excerpt",
        source_id="theme_feed:test_bank",
    )

    selected = select_theme_candidates(
        [repeat_candidate, fresh_candidate],
        max_items=1,
        recent_links={repeat_candidate.link},
        recent_topic_tokens=[frozenset({"japan", "official", "warn", "volatility"})],
    )

    assert selected == [repeat_candidate]


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
    rendered = render_markdown(result.data)
    assert "[Liberty Street Economics](https://libertystreeteconomics.newyorkfed.org/)" in rendered
    assert "Theme Radar: selected 2 items from live RSS/search sources: FRED Blog, Liberty Street Economics." in rendered


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


def test_live_theme_radar_avoids_links_selected_before_today(tmp_path) -> None:
    history_path = tmp_path / "theme_history.json"
    history_path.write_text(
        json.dumps(
            [
                {
                    "selected_date": "2026-06-09",
                    "title": "Why exclude food and energy from inflation measures?",
                    "source": "FRED Blog",
                    "link": "https://fredblog.stlouisfed.org/example/core-pce/",
                    "source_depth": "RSS excerpt",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = replace_theme_radar_with_live(
        build_sample_brief_data(),
        run_date=date(2026, 6, 10),
        history_path=history_path,
        client_factory=FakeThemeClient,
        sources=_theme_sources_with_third(),
    )

    titles = [item.title for item in result.data.theme_radar]

    assert "Why exclude food and energy from inflation measures?" not in titles
    assert len(titles) == 2
    assert result.recent_repeat_titles == []
    assert result.recent_topic_repeat_titles == []


def test_live_theme_radar_avoids_recent_near_duplicate_topics(tmp_path) -> None:
    history_path = tmp_path / "theme_history.json"
    history_path.write_text(
        json.dumps(
            [
                {
                    "selected_date": "2026-06-09",
                    "title": "Japan officials warn on yen volatility as USD/JPY rises",
                    "source": "Reuters via Google News",
                    "link": "https://news.google.com/rss/articles/example-yen-warning",
                    "source_depth": "search result snippet",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = replace_theme_radar_with_live(
        build_sample_brief_data(),
        run_date=date(2026, 6, 10),
        history_path=history_path,
        client_factory=SimilarThemeClient,
        sources=[
            ThemeSource("Japan FX Source", "https://similar-yen.test/feed/", "theme_feed:test_similar_yen"),
            *_theme_sources(),
        ],
    )

    titles = [item.title for item in result.data.theme_radar]

    assert "Japan finance ministry warns again on yen volatility" not in titles
    assert "Why exclude food and energy from inflation measures?" in titles
    assert "Why Does the U.S. Always Run a Trade Deficit?" in titles
    assert result.recent_topic_repeat_titles == []


def test_live_theme_radar_allows_same_day_repeats(tmp_path) -> None:
    history_path = tmp_path / "theme_history.json"
    history_path.write_text(
        json.dumps(
            [
                {
                    "selected_date": "2026-06-10",
                    "title": "Why exclude food and energy from inflation measures?",
                    "source": "FRED Blog",
                    "link": "https://fredblog.stlouisfed.org/example/core-pce/",
                    "source_depth": "RSS excerpt",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = replace_theme_radar_with_live(
        build_sample_brief_data(),
        run_date=date(2026, 6, 10),
        history_path=history_path,
        client_factory=FakeThemeClient,
        sources=_theme_sources_with_third(),
    )

    titles = [item.title for item in result.data.theme_radar]

    assert "Why exclude food and energy from inflation measures?" in titles
    assert result.recent_repeat_titles == []


def test_live_theme_radar_parses_google_news_search_snippets() -> None:
    result = replace_theme_radar_with_live(
        build_sample_brief_data(),
        client_factory=FakeThemeClient,
        sources=[],
        search_queries=[
            ThemeSearchQuery(
                "USD/JPY intervention",
                "USD JPY intervention yen Japan finance ministry",
                "theme_search:test_usdjpy",
            )
        ],
    )

    assert result.data.theme_radar[0].title == "Japan officials warn on yen volatility as USD/JPY rises"
    assert result.data.theme_radar[0].source == "Reuters via Google News"
    assert result.data.theme_radar[0].source_depth == "search result snippet"
    assert "theme_search:test_usdjpy" in result.sources


def test_live_theme_radar_filters_untrusted_google_news_sources() -> None:
    moomoo_feed = GOOGLE_NEWS_FEED.replace("Reuters", "Moomoo")

    class MoomooOnlyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url):
            return FakeResponse(text=moomoo_feed)

    result = replace_theme_radar_with_live(
        build_sample_brief_data(),
        client_factory=MoomooOnlyClient,
        sources=[],
        search_queries=[
            ThemeSearchQuery(
                "USD/JPY intervention",
                "USD JPY intervention yen Japan finance ministry",
                "theme_search:test_usdjpy",
            )
        ],
    )

    assert result.data.theme_radar == []
    assert result.fallback_used is True
    assert result.candidate_count == 0


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
        theme_history_path=tmp_path / "theme_history.json",
        theme_recent_days=7,
        portfolio_path=tmp_path / "positions.csv",
        output_dir=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
    )

    def fake_replace_theme(data, **_kwargs):
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
