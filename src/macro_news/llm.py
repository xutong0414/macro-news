from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace

import httpx

from .config import Settings
from .costing import TokenUsage, estimate_llm_cost_usd
from .sample_data import BriefData, ThemeItem

PROMPT_VERSION = "gemini_narrative_v1"


@dataclass(frozen=True)
class SynthesisResult:
    data: BriefData
    token_usage: TokenUsage
    estimated_cost_usd: float
    provider: str
    model: str
    prompt_version: str


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:'\w+)?\b", text))


def _require_word_range(label: str, text: str, minimum: int, maximum: int) -> None:
    count = word_count(text)
    if count < minimum or count > maximum:
        raise ValueError(f"{label} must be {minimum}-{maximum} words; got {count}")


def _require_word_max(label: str, text: str, maximum: int) -> None:
    count = word_count(text)
    if count > maximum:
        raise ValueError(f"{label} must be <= {maximum} words; got {count}")


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Gemini response did not contain a JSON object")
    return json.loads(cleaned[start : end + 1])


def _normalize_book_impact(text: str) -> str:
    prefix = "What this means for our book:"
    stripped = text.strip()
    if stripped.lower().startswith(prefix.lower()):
        return stripped
    return f"{prefix} {stripped}"


def build_narrative_prompt(data: BriefData) -> str:
    facts = {
        "market_dashboard": [asdict(row) for row in data.market_rows],
        "calendar": [asdict(event) for event in data.calendar],
        "chart_caption": data.chart_caption,
        "theme_inputs": [asdict(item) for item in data.theme_radar],
        "assumptions": data.assumptions,
    }

    return (
        "You are writing a Daily Macro Brief for a time-poor macro portfolio manager.\n"
        "Use only the facts below. Do not invent market numbers, source names, links, or positions.\n"
        "Keep the tone concise, investment-oriented, and opinionated.\n\n"
        "Return only valid JSON with this exact shape:\n"
        "{\n"
        '  "three_things": ["string", "string", "string"],\n'
        '  "theme_radar": [\n'
        '    {"title": "string", "source": "string", "link": "string", "summary": "string", "book_impact": "string"}\n'
        "  ],\n"
        '  "contrarian_corner": "string"\n'
        "}\n\n"
        "Constraints:\n"
        "- Each item in three_things must be 80 words or fewer and include a clear 'So what:' clause.\n"
        "- theme_radar must contain 1-3 items and reuse the provided title, source, and link values.\n"
        "- Each theme_radar summary must be 60-100 words and explain the author's thesis and evidence.\n"
        "- Each book_impact line must start with 'What this means for our book:'.\n"
        "- contrarian_corner must be 50-100 words.\n\n"
        f"Facts:\n{json.dumps(facts, indent=2)}"
    )


def parse_narrative_response(text: str, base_data: BriefData) -> BriefData:
    payload = _extract_json(text)

    three_things = payload.get("three_things")
    if not isinstance(three_things, list) or len(three_things) != 3:
        raise ValueError("Gemini response must include exactly three items in three_things")
    three_things = [str(item).strip() for item in three_things]
    for idx, item in enumerate(three_things, 1):
        if "so what:" not in item.lower():
            raise ValueError(f"three_things item {idx} must include 'So what:'")
        _require_word_max(f"three_things item {idx}", item, 80)

    allowed_theme_meta = {(item.title, item.source, item.link) for item in base_data.theme_radar}
    theme_payload = payload.get("theme_radar")
    if not isinstance(theme_payload, list) or not 1 <= len(theme_payload) <= 3:
        raise ValueError("Gemini response must include 1-3 theme_radar items")

    theme_radar: list[ThemeItem] = []
    for idx, item in enumerate(theme_payload, 1):
        if not isinstance(item, dict):
            raise ValueError(f"theme_radar item {idx} must be an object")
        title = str(item.get("title", "")).strip()
        source = str(item.get("source", "")).strip()
        link = str(item.get("link", "")).strip()
        summary = str(item.get("summary", "")).strip()
        book_impact = _normalize_book_impact(str(item.get("book_impact", "")))

        if (title, source, link) not in allowed_theme_meta:
            raise ValueError(f"theme_radar item {idx} must reuse an existing title, source, and link")
        _require_word_range(f"theme_radar summary {idx}", summary, 60, 100)
        theme_radar.append(
            ThemeItem(
                title=title,
                source=source,
                link=link,
                summary=summary,
                book_impact=book_impact,
            )
        )

    contrarian_corner = str(payload.get("contrarian_corner", "")).strip()
    _require_word_range("contrarian_corner", contrarian_corner, 50, 100)

    return replace(
        base_data,
        three_things=three_things,
        theme_radar=theme_radar,
        contrarian_corner=contrarian_corner,
        data_sources=[*base_data.data_sources, "gemini_synthesis"],
    )


def synthesize_with_gemini(settings: Settings, data: BriefData) -> SynthesisResult:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required when --use-llm is set")

    prompt = build_narrative_prompt(data)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }

    try:
        response = httpx.post(
            url,
            headers={"x-goog-api-key": settings.gemini_api_key},
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    body = response.json()
    candidates = body.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    if not text.strip():
        raise RuntimeError("Gemini returned an empty text response")

    generated_data = parse_narrative_response(text, data)
    usage_metadata = body.get("usageMetadata", {})
    usage = TokenUsage(
        input_tokens=int(usage_metadata.get("promptTokenCount", 0)),
        output_tokens=int(usage_metadata.get("candidatesTokenCount", 0)),
        total_tokens=int(usage_metadata.get("totalTokenCount", 0)),
        provider="gemini",
    )
    estimated_cost = estimate_llm_cost_usd("gemini", settings.gemini_model, usage)

    return SynthesisResult(
        data=generated_data,
        token_usage=usage,
        estimated_cost_usd=estimated_cost,
        provider="gemini",
        model=settings.gemini_model,
        prompt_version=PROMPT_VERSION,
    )

