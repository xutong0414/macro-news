from __future__ import annotations

import html
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from .sample_data import BriefData


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


def _three_things_news_query(item: str) -> str:
    lowered = item.lower()
    if any(term in lowered for term in ("usd/jpy", "intervention", "yen reversal", "yen appreciation")):
        return "USD JPY Japan intervention yield spread"
    if any(term in lowered for term in ("em debt", "em duration", "em financing", "emerging market")) and any(
        term in lowered for term in ("s&p", "equities", "risk-off", "risk aversion", "risk assets")
    ):
        return "emerging market debt US yields dollar"
    if any(term in lowered for term in ("us 10y", "treasury", "higher us yields", "yields rose", "yield differential")):
        return "US 10Y yields gold EM debt"
    if any(term in lowered for term in ("dxy", "dollar strength", "broad dollar", "usd funding")):
        return "US dollar index DXY EM debt gold"
    if any(term in lowered for term in ("em debt", "em duration", "em financing", "emerging market")):
        return "emerging market debt US yields dollar"
    if any(term in lowered for term in ("s&p", "equities", "risk-off", "risk assets")):
        return "global equities risk off US yields dollar"
    if "gold" in lowered:
        return "gold US yields dollar"
    if "oil" in lowered or "inflation" in lowered:
        return "oil inflation rates market"
    if any(term in lowered for term in ("dxy", "dollar")):
        return "US dollar index DXY market news"
    return "macro markets rates FX"


def _three_thing_news_link(item: str) -> str:
    return f"https://finance.yahoo.com/search?p={quote_plus(_three_things_news_query(item))}"


def _three_thing_title(item: str) -> str:
    lowered = item.lower()
    if any(term in lowered for term in ("usd/jpy", "intervention", "yen reversal", "yen appreciation")):
        return "USD/JPY Intervention Risk"
    if any(term in lowered for term in ("us 10y", "treasury", "higher us yields", "yields rose")) and any(
        term in lowered for term in ("dxy", "dollar", "gold", "em debt", "em financing")
    ):
        return "Rates And Dollar Pressure"
    if any(term in lowered for term in ("s&p", "equities", "risk-off", "risk aversion", "risk assets")):
        return "Risk Tone Turns Defensive"
    if "gold" in lowered:
        return "Gold Under Rate Pressure"
    if any(term in lowered for term in ("em debt", "em duration", "emerging market")):
        return "EM Debt Faces Tighter Conditions"
    if "oil" in lowered or "inflation" in lowered:
        return "Oil Keeps Inflation Risk Alive"
    if any(term in lowered for term in ("dxy", "dollar")):
        return "Dollar Strength Tightens Conditions"
    return "Macro Signal To Watch"


def _render_three_things_markdown(items: list[str]) -> str:
    blocks: list[str] = []
    for idx, item in enumerate(items, 1):
        main, so_what = _split_so_what(item)
        parts = [f"### {idx}. {_three_thing_title(item)}", main]
        if so_what:
            implication = so_what.removeprefix("So what:").strip()
            parts.append(f"**So what:** {implication}")
        parts.append(f"**Read more:** [Yahoo Finance]({_three_thing_news_link(item)})")
        blocks.append("\n\n".join(parts))
    return "\n\n".join(blocks)


def _chart_reading(data: BriefData) -> str:
    caption = data.chart_caption.strip()
    prefix = "This chart supports the first thing that matters today (see above)."
    return f"{prefix} {caption}" if caption else prefix


def render_markdown(data: BriefData, run_date: date | None = None) -> str:
    run_date = run_date or date.today()
    market_table = _table(
        ["Asset", "Close", "Prior", "Change", "Reading"],
        [[r.asset, r.close, r.prior, r.change, r.so_what] for r in data.market_rows],
    )
    calendar_table = _table(
        ["Session", "Time", "Event", "Consensus", "Why it matters"],
        [[e.session, e.time, e.event, e.consensus, e.why_it_matters] for e in data.calendar],
    )
    three = _render_three_things_markdown(data.three_things)
    themes = "\n\n".join(
        (
            f"### {item.title}\n"
            f"Source: [{item.source}]({item.link})\n\n"
            f"{item.summary}\n\n"
            f"{item.book_impact}"
        )
        for item in data.theme_radar
    )
    assumptions = "\n".join(f"- {item}" for item in data.assumptions)
    dashboard_notes = "\n".join(f"- {item}" for item in data.dashboard_notes)
    dashboard_notes_section = f"""
Dashboard notes:

{dashboard_notes}
""" if dashboard_notes else ""
    source_notes = "\n".join(f"- {item}" for item in data.source_notes)
    source_status_section = f"""
## Source Status

{source_notes}
""" if source_notes else ""

    return f"""# Daily Macro Brief - {run_date.isoformat()}

## Overnight Market Dashboard

{market_table}
{dashboard_notes_section}

## The 3 Things That Matter Today

{three}

## Today's Calendar / Next Session

{calendar_table}

## One Chart Worth Seeing

![USD/JPY in Five Days](chart.png)

**Reading:** {_chart_reading(data)}

## Theme Radar

{themes}

## Contrarian Corner

{data.contrarian_corner}
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
        "body{font-family:Arial,sans-serif;line-height:1.45;color:#111827;max-width:880px;margin:24px auto;padding:0 18px}",
        "table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #d1d5db;padding:8px;text-align:left;vertical-align:top}",
        "th{background:#f3f4f6}h1,h2,h3{line-height:1.2}h3{font-size:18px;margin:22px 0 6px}img{max-width:100%;height:auto}",
        ".reading,.note-line,.read-more{color:#4b5563;font-size:14px}.note-line,.read-more{margin:4px 0 0 18px}",
        ".read-more{margin-bottom:18px}",
        "</style>",
        "</head>",
        "<body>",
    ]

    in_table = False
    table_rows: list[str] = []

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
            html_lines.append("<tr>" + "".join(f"<{tag}>{html.escape(cell)}</{tag}>" for cell in cells) + "</tr>")
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
            html_lines.append(f"<h1>{_inline_markdown_to_html(line[2:])}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{_inline_markdown_to_html(line[3:])}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{_inline_markdown_to_html(line[4:])}</h3>")
        elif line.startswith("!["):
            html_lines.append('<img src="chart.png" alt="USD/JPY in Five Days">')
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

    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.plot(labels, values, marker="o", linewidth=2, color="#2563eb")
    ax.set_title("USD/JPY in Five Days")
    ax.set_ylabel("Spot")
    ax.grid(True, alpha=0.25)
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
