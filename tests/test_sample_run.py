from __future__ import annotations

from macro_news.config import Settings, normalize_timezone
from macro_news.render import render_markdown
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
        output_dir=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
    )

    result = run_brief(settings, send=False)

    assert result.delivery_status == "dry_run"
    assert result.output_paths["latest_markdown"].exists()
    assert result.output_paths["latest_html"].exists()
    assert result.output_paths["latest_chart"].exists()
    assert result.log_path.exists()
