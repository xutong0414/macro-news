from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MarketRow:
    asset: str
    close: str
    prior: str
    change: str
    so_what: str


@dataclass(frozen=True)
class CalendarEvent:
    session: str
    time: str
    event: str
    consensus: str
    why_it_matters: str


@dataclass(frozen=True)
class ThemeItem:
    title: str
    source: str
    link: str
    summary: str
    book_impact: str


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


def build_sample_brief_data() -> BriefData:
    return BriefData(
        market_rows=[
            MarketRow("S&P 500", "5,412", "5,389", "+0.4%", "Risk tone is constructive but not broad enough to chase beta."),
            MarketRow("Euro Stoxx 50", "5,020", "4,995", "+0.5%", "Europe is following the US lead, with cyclicals still rate-sensitive."),
            MarketRow("US 10Y yield", "4.42%", "4.36%", "+6 bp", "Higher duration pressure matters for gold and EM duration."),
            MarketRow("Germany 10Y yield", "2.61%", "2.58%", "+3 bp", "Bunds confirm the global rates move rather than a US-only story."),
            MarketRow("DXY", "104.8", "104.3", "+0.5%", "Dollar strength supports long USD/JPY but tightens EM conditions."),
            MarketRow("USD/JPY", "157.20", "156.10", "+0.7%", "Position is working, but intervention headlines remain the tail risk."),
            MarketRow("Gold", "$2,352", "$2,371", "-0.8%", "Gold is absorbing real-rate pressure, not breaking the trend yet."),
            MarketRow("WTI oil", "$78.40", "$77.10", "+1.7%", "Oil bounce raises inflation-risk asymmetry for rates."),
            MarketRow("BTC", "$68,900", "$67,500", "+2.1%", "Crypto risk appetite is firm but not central to the assumed book."),
        ],
        three_things=[
            "Rates are doing the heavy lifting overnight. The US 10Y yield rose 6 bp and the dollar firmed, so the book's USD/JPY long is aligned with momentum. So what: keep the FX view, but watch whether real-rate pressure starts to hurt gold more visibly.",
            "Oil is quietly rebuilding an inflation impulse. WTI rose 1.7% in the sample dashboard, which matters because the market narrative still leans toward eventual easing. So what: higher oil can delay rate relief and pressure EM duration.",
            "Risk assets are up, but the signal is not cleanly reflationary. Equities and BTC are firmer while gold is softer and yields are higher. So what: this is a dollar-and-rates morning, not a broad risk-on signal.",
        ],
        calendar=[
            CalendarEvent("Asia", "09:30 CST", "China official PMI", "50.1", "A weak print would reinforce China-demand concerns and weigh on commodities."),
            CalendarEvent("Europe", "17:00 CST", "Euro area CPI flash", "2.5% y/y", "Upside surprise would challenge ECB easing confidence."),
            CalendarEvent("US", "20:30 CST", "US core PCE", "0.2% m/m", "The key event for rates, gold, and broad dollar direction."),
            CalendarEvent("US", "22:00 CST", "University of Michigan inflation expectations", "3.1%", "Inflation expectations can amplify or fade the PCE reaction."),
        ],
        chart_caption="USD/JPY keeps grinding higher; intervention risk rises as momentum extends.",
        chart_series=[
            ("Mon", 154.8),
            ("Tue", 155.1),
            ("Wed", 155.7),
            ("Thu", 156.1),
            ("Fri", 157.2),
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
            ),
        ],
        contrarian_corner=(
            "The market may be too comfortable with a clean disinflation path. If oil, freight, or shelter components stop cooperating at the same time that fiscal issuance keeps term premium elevated, the next surprise could be a higher real-rate regime rather than a growth scare. That would favor dollar resilience and punish crowded duration longs."
        ),
        assumptions=[
            "Assumed book is long USD/JPY, overweight gold, and exposed to an EM debt basket.",
            "No real portfolio file is connected yet; book impacts are based on the assumed positions above.",
            "Free/public data feeds are used for v1; unavailable rows are flagged as scaffold fallback rather than silently filled.",
        ],
        data_sources=["sample_market_data", "sample_calendar", "sample_deep_content"],
        source_notes=[
            "Market: sample scaffold rows are used until live market mode is enabled.",
            "Calendar: sample scaffold events are used until live calendar mode is enabled.",
            "Theme Radar: sample source items are used until live RSS mode is enabled.",
        ],
    )
