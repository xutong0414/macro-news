from __future__ import annotations

import html
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

from .sample_data import BriefData


CONTRARIAN_READING_LINKS = [
    ("Yahoo Finance currencies", "https://finance.yahoo.com/markets/currencies/"),
    ("Japan MOF intervention data", "https://www.mof.go.jp/english/policy/international_policy/reference/feio/quarter/index.html"),
    ("BOJ international finance", "https://www.boj.or.jp/en/intl_finance/index.htm"),
]


def _table(headers: list[str], rows: list[list[str]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def _inline_markdown_to_html(text: str) -> str:
    link_pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
    parts: list[str] = []
    cursor = 0
    for match in link_pattern.finditer(text):
        parts.append(html.escape(text[cursor : match.start()]))
        label = html.escape(match.group(1))
        url = html.escape(match.group(2), quote=True)
        parts.append(f'<a href="{url}">{label}</a>')
        cursor = match.end()
    parts.append(html.escape(text[cursor:]))
    return "".join(parts)


def _bold_label_to_html(text: str) -> str:
    escaped = _inline_markdown_to_html(text)
    return re.sub(r"^\*\*([^*]+):\*\*", r"<strong>\1:</strong>", escaped)


def _split_so_what(item: str) -> tuple[str, str]:
    match = re.search(r"\bSo what:\s*", item, flags=re.IGNORECASE)
    if not match:
        return item.strip(), ""
    main = item[: match.start()].strip()
    so_what = item[match.end() :].strip()
    return main, f"So what: {so_what}" if so_what else ""


def _three_thing_read_more(item: str) -> tuple[str, str]:
    lowered = item.lower()
    if any(term in lowered for term in ("usd/jpy", "intervention", "yen reversal", "yen appreciation")):
        return ("Yahoo Finance currencies", "https://finance.yahoo.com/markets/currencies/")
    if any(term in lowered for term in ("em debt", "em duration", "em financing", "emerging market")) and any(
        term in lowered for term in ("s&p", "equities", "risk-off", "risk aversion", "risk assets")
    ):
        return ("Yahoo Finance EMB", "https://finance.yahoo.com/quote/EMB/")
    if any(term in lowered for term in ("us 10y", "treasury", "higher us yields", "yields rose", "yield differential")):
        return ("Yahoo Finance US 10Y", "https://finance.yahoo.com/quote/%5ETNX/")
    if any(term in lowered for term in ("dxy", "dollar strength", "broad dollar", "usd funding")):
        return ("Yahoo Finance currencies", "https://finance.yahoo.com/markets/currencies/")
    if any(term in lowered for term in ("em debt", "em duration", "em financing", "emerging market")):
        return ("Yahoo Finance EMB", "https://finance.yahoo.com/quote/EMB/")
    if any(term in lowered for term in ("s&p", "equities", "risk-off", "risk assets")):
        return ("Yahoo Finance EMB", "https://finance.yahoo.com/quote/EMB/")
    if "gold" in lowered:
        return ("Yahoo Finance gold futures", "https://finance.yahoo.com/quote/GC=F/")
    if "oil" in lowered or "inflation" in lowered:
        return ("Yahoo Finance WTI oil", "https://finance.yahoo.com/quote/CL=F/")
    if any(term in lowered for term in ("dxy", "dollar")):
        return ("Yahoo Finance currencies", "https://finance.yahoo.com/markets/currencies/")
    return ("Yahoo Finance US 10Y", "https://finance.yahoo.com/quote/%5ETNX/")


def _three_thing_title(item: str) -> str:
    lowered = item.lower()
    if any(term in lowered for term in ("usd/jpy", "intervention", "yen reversal", "yen appreciation")):
        return "USD/JPY Intervention Risk"
    if any(term in lowered for term in ("s&p", "equities", "risk-off", "risk aversion", "risk assets")):
        return "Risk Tone Turns Defensive"
    if "gold" in lowered:
        return "Gold Under Rate Pressure"
    if any(term in lowered for term in ("us 10y", "treasury", "higher us yields", "yields rose")) and any(
        term in lowered for term in ("dxy", "dollar", "gold", "em debt", "em financing")
    ):
        return "Rates And Dollar Pressure"
    if any(term in lowered for term in ("em debt", "em duration", "emerging market")):
        return "EM Debt Faces Tighter Conditions"
    if "oil" in lowered or "inflation" in lowered:
        return "Oil Keeps Inflation Risk Alive"
    if any(term in lowered for term in ("dxy", "dollar")):
        return "Dollar Strength Tightens Conditions"
    return "Macro Signal To Watch"


def _status_asset_name(asset: str, status: str) -> str:
    if status in {"*", "†"}:
        return f"{asset} {status}"
    return asset


def _event_markdown(event: str, link: str) -> str:
    return f"[{event}]({link})" if link else event


def _theme_book_impact(text: str) -> str:
    prefix = "What this means for our book:"
    stripped = text.strip()
    if stripped.lower().startswith(prefix.lower()):
        stripped = stripped[len(prefix) :].strip()
    return f"**For Our Book:** {stripped}"


def _contrarian_further_reading() -> str:
    links = ", ".join(f"[{label}]({url})" for label, url in CONTRARIAN_READING_LINKS)
    return f"**Further reading:** {links}"


def _report_time_line(data: BriefData) -> str:
    return f"\nUpdated as of: {data.report_time}\n" if data.report_time else ""


def _calendar_status_notes(data: BriefData) -> str:
    statuses = {event.status for event in data.calendar if event.status}
    if not statuses:
        return ""
    note_by_status = {
        "Live": "Live = event is dated today in the calendar source.",
        "*": "* = next-session or nearest source-week item, usually because today is a weekend/holiday or same-day options are thin.",
        "†": "† = cached real calendar row after live refresh failed.",
    }
    notes = [note_by_status[status] for status in ("Live", "*")]
    if "†" in statuses:
        notes.append(note_by_status["†"])
    return "\nCalendar status notes:\n\n" + "\n".join(f"- {note}" for note in notes)


def _categorized_assumptions(items: list[str]) -> str:
    portfolio: list[str] = []
    data_handling: list[str] = []
    source_coverage: list[str] = []
    other: list[str] = []

    for item in items:
        lowered = item.lower()
        if any(key in lowered for key in ("portfolio file", "position carry-forward", "assignment pdf assumption", "assumed book", "portfolio file is connected")):
            portfolio.append(item)
        elif any(key in lowered for key in ("market dashboard", "calendar", "theme radar", "live mode", "scaffold", "blank")):
            data_handling.append(item)
        elif any(key in lowered for key in ("source", "feed", "public")):
            source_coverage.append(item)
        else:
            other.append(item)

    sections = [
        ("Portfolio / Book", portfolio),
        ("Data Handling", data_handling),
        ("Source Coverage", source_coverage),
        ("Other", other),
    ]
    blocks: list[str] = []
    for heading, values in sections:
        if values:
            blocks.append(f"### {heading}\n\n" + "\n".join(f"- {value}" for value in values))
    return "\n\n".join(blocks)


def _feedback_rows(data: BriefData) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    rows.append(("Dashboard", "Overnight market dashboard"))
    rows.extend((f"Three Things #{idx}", _three_thing_title(item)) for idx, item in enumerate(data.three_things, 1))
    rows.extend(("Calendar", event.event) for event in data.calendar)
    rows.append(("Chart", "USD/JPY: 3-Month Trend"))
    rows.extend(("Theme Radar", item.title) for item in data.theme_radar)
    rows.append(("Contrarian Corner", "Main argument and trigger"))
    return rows


def _feedback_questionnaire(data: BriefData) -> str:
    rows = "\n".join(f"| {section} | {item} |  |  |" for section, item in _feedback_rows(data))
    return f"""## Feedback Questionnaire

Please paste this compact format into Excel/CSV and share your feedback with Tong Xu for further refinement. Usefulness scale: 1 = not useful, 5 = very useful.

| Section | Item | Usefulness 1-5 | Comment |
| --- | --- | --- | --- |
{rows}"""


def _render_three_things_markdown(items: list[str]) -> str:
    blocks: list[str] = []
    for idx, item in enumerate(items, 1):
        main, so_what = _split_so_what(item)
        parts = [f"### {idx}. {_three_thing_title(item)}", main]
        if so_what:
            implication = so_what.removeprefix("So what:").strip()
            parts.append(f"**So what:** {implication}")
        label, url = _three_thing_read_more(item)
        parts.append(f"**Read more:** [{label}]({url})")
        blocks.append("\n\n".join(parts))
    return "\n\n".join(blocks)


def _chart_reading(data: BriefData) -> str:
    caption = data.chart_caption.strip()
    prefix = "This chart supports the first thing that matters today (see above); the latest five observations are highlighted."
    return f"{prefix} {caption}" if caption else prefix


def _chart_source_note(data: BriefData) -> str:
    if any(source.startswith("frankfurter:USDJPY") for source in data.data_sources):
        return "**Data source:** [Frankfurter USD/JPY daily reference rates](https://frankfurter.dev/)"
    return "**Data source:** sample USD/JPY series"


def render_markdown(data: BriefData, run_date: date | None = None) -> str:
    run_date = run_date or date.today()
    market_table = _table(
        ["Asset", "Close", "Prior", "Change", "As of", "Reading"],
        [[_status_asset_name(r.asset, r.status), r.close, r.prior, r.change, r.as_of, r.so_what] for r in data.market_rows],
    )
    calendar_table = _table(
        ["Session", "Event date", "Time", "Event", "Consensus", "Status", "Why it matters"],
        [[e.session, e.event_date, e.time, _event_markdown(e.event, e.link), e.consensus, e.status, e.why_it_matters] for e in data.calendar],
    )
    three = _render_three_things_markdown(data.three_things)
    themes = "\n\n".join(
        (
            f"### {item.title}\n"
            f"Source: [{item.source}]({item.link}) | Source depth: {item.source_depth}\n\n"
            f"{item.summary}\n\n"
            f"{_theme_book_impact(item.book_impact)}"
        )
        for item in data.theme_radar
    )
    assumptions = _categorized_assumptions(data.assumptions)
    dashboard_notes = "\n".join(f"- {item}" for item in data.dashboard_notes)
    dashboard_notes_section = f"""
Dashboard notes:

{dashboard_notes}
""" if dashboard_notes else ""
    calendar_status_notes = _calendar_status_notes(data)
    source_notes = "\n".join(f"- {item}" for item in data.source_notes)
    source_status_section = f"""
## Source Status

{source_notes}
""" if source_notes else ""

    return f"""# Daily Macro Brief - {run_date.isoformat()}
{_report_time_line(data)}

## Overnight Market Dashboard

{market_table}
{dashboard_notes_section}

## The 3 Things That Matter Today

{three}

## Today's Calendar / Next Session

{calendar_table}
{calendar_status_notes}

## One Chart Worth Seeing

![USD/JPY: 3-Month Trend](chart.png)

**Reading:** {_chart_reading(data)}

{_chart_source_note(data)}

## Theme Radar

{themes}

## Contrarian Corner

{data.contrarian_corner}

{_contrarian_further_reading()}

{_feedback_questionnaire(data)}
{source_status_section}

## Assumptions

{assumptions}
"""


def render_html(data: BriefData, run_date: date | None = None) -> str:
    markdown = render_markdown(data, run_date)
    lines = markdown.splitlines()
    html_lines: list[str] = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Daily Macro Brief</title>",
        "<style>",
        "body{font-family:Arial,sans-serif;font-size:16px;line-height:1.45;color:#111827;max-width:880px;margin:24px auto;padding:0 18px}",
        "p{font-size:16px;margin:0 0 14px}",
        "table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #d1d5db;padding:8px;text-align:left;vertical-align:top}",
        "th{background:#f3f4f6}h1,h2,h3{line-height:1.2}h3{font-size:18px;margin:22px 0 6px}img{max-width:100%;height:auto}",
        ".reading,.note-line{color:#111827;font-size:16px;margin:8px 0 12px 18px}",
        ".read-more{color:#4b5563;font-size:14px;margin:4px 0 18px 18px}",
        ".footnote-heading{color:#4b5563;font-size:13px;font-weight:bold;margin:12px 0 4px}",
        ".footnote{color:#4b5563;font-size:13px;line-height:1.35;margin:3px 0 0 18px}",
        "</style>",
        "</head>",
        "<body>",
    ]

    in_table = False
    table_rows: list[str] = []
    footnote_block = False

    def flush_table() -> None:
        nonlocal in_table, table_rows
        if not in_table:
            return
        html_lines.append("<table>")
        for idx, row in enumerate(table_rows):
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            if idx == 1 and all(set(cell) <= {"-"} for cell in cells):
                continue
            tag = "th" if idx == 0 else "td"
            html_lines.append("<tr>" + "".join(f"<{tag}>{_inline_markdown_to_html(cell)}</{tag}>" for cell in cells) + "</tr>")
        html_lines.append("</table>")
        in_table = False
        table_rows = []

    for line in lines:
        if line.startswith("| "):
            in_table = True
            table_rows.append(line)
            continue
        flush_table()
        if not line.strip():
            continue
        if line.startswith("# "):
            footnote_block = False
            html_lines.append(f"<h1>{_inline_markdown_to_html(line[2:])}</h1>")
        elif line.startswith("## "):
            footnote_block = False
            html_lines.append(f"<h2>{_inline_markdown_to_html(line[3:])}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{_inline_markdown_to_html(line[4:])}</h3>")
        elif line.startswith("!["):
            html_lines.append('<img src="chart.png" alt="USD/JPY: 3-Month Trend">')
        elif line.startswith("**Reading:"):
            html_lines.append(f'<p class="reading">{_bold_label_to_html(line)}</p>')
        elif line.startswith("Reading:"):
            html_lines.append(f'<p class="reading">{_inline_markdown_to_html(line)}</p>')
        elif line.startswith("Caption:"):
            html_lines.append(f'<p class="reading">{_inline_markdown_to_html(line)}</p>')
        elif line.startswith("**So what:"):
            html_lines.append(f'<p class="note-line">{_bold_label_to_html(line)}</p>')
        elif line.startswith("**Read more:"):
            html_lines.append(f'<p class="read-more">{_bold_label_to_html(line)}</p>')
        elif line.startswith("**Further reading:"):
            html_lines.append(f'<p class="read-more">{_bold_label_to_html(line)}</p>')
        elif line.startswith("**Data source:"):
            html_lines.append(f'<p class="read-more">{_bold_label_to_html(line)}</p>')
        elif line.startswith("**For Our Book:"):
            html_lines.append(f'<p class="note-line">{_bold_label_to_html(line)}</p>')
        elif line in {"Dashboard notes:", "Calendar status notes:"}:
            footnote_block = True
            html_lines.append(f'<p class="footnote-heading">{_inline_markdown_to_html(line)}</p>')
        elif line.startswith("- ") and footnote_block:
            html_lines.append(f'<p class="footnote">{_inline_markdown_to_html(line)}</p>')
        elif line.startswith("- "):
            html_lines.append(f"<p>{_inline_markdown_to_html(line)}</p>")
        else:
            html_lines.append(f"<p>{_inline_markdown_to_html(line)}</p>")
    flush_table()
    html_lines.extend(["</body>", "</html>"])
    return "\n".join(html_lines)


def write_chart(data: BriefData, chart_path: Path) -> None:
    cache_root = Path(".cache").resolve()
    mpl_cache_dir = cache_root / "matplotlib"
    cache_root.mkdir(parents=True, exist_ok=True)
    mpl_cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_root))
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache_dir))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [point[0] for point in data.chart_series]
    values = [point[1] for point in data.chart_series]
    parsed_dates: list[datetime] = []
    for label in labels:
        try:
            parsed_dates.append(datetime.fromisoformat(label))
        except ValueError:
            parsed_dates = []
            break
    x_values = parsed_dates if len(parsed_dates) == len(labels) else list(range(len(labels)))
    recent_start = max(len(values) - 5, 0)

    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.plot(x_values, values, linewidth=1.8, color="#9ca3af", label="Full history")
    ax.plot(x_values[recent_start:], values[recent_start:], marker="o", linewidth=2.4, color="#2563eb", label="Latest 5 observations")
    ax.set_title("USD/JPY: 3-Month Trend")
    ax.set_ylabel("Spot")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, loc="best", fontsize=8)
    if parsed_dates:
        fig.autofmt_xdate(rotation=30, ha="right")
    else:
        ax.set_xticks(x_values)
        ax.set_xticklabels(labels, rotation=30, ha="right")
    fig.tight_layout()
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(chart_path, dpi=160)
    plt.close(fig)


def write_outputs(data: BriefData, output_dir: Path, run_date: date | None = None) -> dict[str, Path]:
    run_date = run_date or date.today()
    latest_dir = output_dir / "latest"
    archive_dir = output_dir / "archive" / run_date.isoformat()
    latest_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "latest_markdown": latest_dir / "brief.md",
        "latest_html": latest_dir / "brief.html",
        "latest_chart": latest_dir / "chart.png",
        "archive_markdown": archive_dir / "brief.md",
        "archive_html": archive_dir / "brief.html",
        "archive_chart": archive_dir / "chart.png",
    }

    markdown = render_markdown(data, run_date)
    html_doc = render_html(data, run_date)

    for key in ("latest_markdown", "archive_markdown"):
        paths[key].write_text(markdown, encoding="utf-8")
    for key in ("latest_html", "archive_html"):
        paths[key].write_text(html_doc, encoding="utf-8")
    for key in ("latest_chart", "archive_chart"):
        write_chart(data, paths[key])

    return paths


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
