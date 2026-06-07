from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MarketRow:
    asset: str
    close: str
    prior: str
    change: str
    so_what: str
    as_of: str = ""
    status: str = ""


@dataclass(frozen=True)
class CalendarEvent:
    session: str
    time: str
    event: str
    consensus: str
    why_it_matters: str
    event_date: str = ""
    status: str = ""
    link: str = ""


@dataclass(frozen=True)
class ThemeItem:
    title: str
    source: str
    link: str
    summary: str
    book_impact: str
    source_depth: str = "Sample scaffold"


@dataclass(frozen=True)
class BriefData:
    market_rows: list[MarketRow]
    three_things: list[str]
    calendar: list[CalendarEvent]
    chart_caption: str
    theme_radar: list[ThemeItem]
    contrarian_corner: str
    chart_series: list[tuple[str, float]]
    assumptions: list[str]
    data_sources: list[str]
    source_notes: list[str] = field(default_factory=list)
    dashboard_notes: list[str] = field(default_factory=list)
    report_time: str = ""


def build_sample_brief_data() -> BriefData:
    return BriefData(
        market_rows=[
            MarketRow("S&P 500", "5,412", "5,389", "+0.4%", "Risk tone improved; EM beta has some support if rates and the dollar stay contained."),
            MarketRow("Euro Stoxx 50", "5,020", "4,995", "+0.5%", "Eurozone risk appetite is firming, a useful cross-check against the US equity signal."),
            MarketRow("US 10Y yield", "4.42%", "4.36%", "+6 bp", "Higher Treasury yields pressure gold and EM duration, while keeping dollar carry supported."),
            MarketRow("Japan 10Y yield", "2.67%", "2.65%", "+2 bp", "Higher JGB yields put Japan-rate pressure on the long USD/JPY view; compare against the US yield move."),
            MarketRow("DXY", "104.8", "104.3", "+0.5%", "Dollar strength tightens EM financing conditions and is a headwind for gold and commodities."),
            MarketRow("EUR/USD", "1.0850", "1.0800", "+0.5%", "Euro firmness trims broad-dollar pressure; confirm with DXY before adding USD exposure."),
            MarketRow("USD/JPY", "157.20", "156.10", "+0.7%", "The long is working, but extension raises intervention and crowded-position risk."),
            MarketRow("Gold", "$2,352", "$2,371", "-0.8%", "Gold weakness shows rate or dollar pressure is biting the overweight."),
            MarketRow("WTI oil", "$78.40", "$77.10", "+1.7%", "Oil strength adds inflation risk and can delay the easing impulse rates want to price."),
            MarketRow("BTC", "$68,900", "$67,500", "+2.1%", "Speculative risk appetite is firm, but this remains a cross-check rather than a core book driver."),
        ],
        three_things=[
            "Rates are doing the heavy lifting overnight. The US 10Y yield rose 6 bp and the dollar firmed, so the book's USD/JPY long is aligned with momentum. So what: keep the FX view, but watch whether rate pressure starts to hurt gold more visibly.",
            "Oil is quietly rebuilding an inflation impulse. WTI rose 1.7% in the sample dashboard, which matters because the market narrative still leans toward eventual easing. So what: higher oil can delay rate relief and pressure EM duration.",
            "Risk assets are up, but the signal is not cleanly reflationary. Equities and BTC are firmer while gold is softer and yields are higher. So what: this is a dollar-and-rates morning, not a broad risk-on signal.",
        ],
        calendar=[
            CalendarEvent("Asia", "09:30 CST", "China official PMI", "50.1", "A weak print would reinforce China-demand concerns and weigh on commodities."),
            CalendarEvent("Europe", "17:00 CST", "Euro area CPI flash", "2.5% y/y", "Upside surprise would challenge ECB easing confidence."),
            CalendarEvent("US", "20:30 CST", "US core PCE", "0.2% m/m", "The key event for rates, gold, and broad dollar direction."),
            CalendarEvent("US", "22:00 CST", "University of Michigan inflation expectations", "3.1%", "Inflation expectations can amplify or fade the PCE reaction."),
        ],
        chart_caption="Spot is extended enough that intervention risk is now the point of the chart.",
        chart_series=[
            ("2026-03-06", 149.3),
            ("2026-03-13", 150.2),
            ("2026-03-20", 151.0),
            ("2026-03-27", 150.7),
            ("2026-04-03", 151.8),
            ("2026-04-10", 152.4),
            ("2026-04-17", 153.1),
            ("2026-04-24", 153.7),
            ("2026-05-01", 154.2),
            ("2026-05-08", 154.8),
            ("2026-05-15", 155.1),
            ("2026-05-22", 156.1),
            ("2026-05-29", 157.2),
        ],
        theme_radar=[
            ThemeItem(
                title="The term premium refuses to disappear",
                source="Sample macro research note",
                link="https://example.com/research/term-premium",
                summary=(
                    "The author argues that fiscal supply and reduced central-bank balance-sheet support are keeping the long end vulnerable. "
                    "The evidence is a mix of auction tails, dealer balance-sheet constraints, and resilient breakevens. This is not a simple growth story; it is about the market demanding more compensation for duration risk."
                    " The note also says positioning has not fully adjusted, leaving rallies vulnerable when supply headlines return."
                ),
                book_impact="What this means for our book: duration pressure supports USD/JPY but can challenge the gold overweight.",
                source_depth="Sample scaffold",
            ),
            ThemeItem(
                title="EM debt is underpricing dollar persistence",
                source="Sample buy-side letter",
                link="https://example.com/letters/em-dollar",
                summary=(
                    "The letter says EM local debt investors are treating dollar strength as temporary, while external funding conditions remain tight. "
                    "It points to weaker reserve accumulation, sticky US real yields, and crowded carry positioning. The core thesis is that EM debt can rally only if dollar strength fades decisively."
                    " The author favors countries with credible disinflation, current-account cushions, and less need for external refinancing."
                ),
                book_impact="What this means for our book: keep EM debt exposure selective and hedge dollar-sensitive legs.",
                source_depth="Sample scaffold",
            ),
        ],
        contrarian_corner=(
            "The market may be too comfortable with a clean disinflation path. If oil, freight, or shelter components stop cooperating at the same time that fiscal issuance keeps term premium elevated, the next surprise could be a higher-rate regime rather than a growth scare. That would favor dollar resilience and punish crowded duration longs."
        ),
        assumptions=[
            "Assumed book is long USD/JPY, overweight gold, and exposed to an EM debt basket.",
            "No real portfolio file is connected yet; book impacts are based on the assumed positions above.",
            "Live mode leaves unavailable market/calendar values blank rather than filling them with scaffold data.",
        ],
        data_sources=["sample_market_data", "sample_calendar", "sample_deep_content"],
        source_notes=[
            "Market: sample scaffold rows are used until live market mode is enabled.",
            "Calendar: sample scaffold events are used until live calendar mode is enabled.",
            "Theme Radar: sample source items are used until live RSS mode is enabled.",
        ],
        dashboard_notes=[
            "Dashboard scope: equities, rates, FX, gold, oil, and BTC are included because those are the PDF-required overnight market blocks.",
            "Timing basis: sample scaffold values are placeholders; live mode replaces them with source-level close/prior or query-time values where available.",
            "Sources: live mode uses public/free data feeds and records live, older-source-date, cached, or blank-row status in the brief and run log.",
        ],
    )
