from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace

import httpx

from .config import Settings
from .costing import TokenUsage, estimate_llm_cost_usd
from .sample_data import BriefData, MarketRow, ThemeItem

PROMPT_VERSION = "gemini_narrative_v32"


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


def _trim_words(text: str, maximum: int) -> str:
    words = re.findall(r"\b\w+(?:'\w+)?\b|[^\w\s]", text)
    word_seen = 0
    kept: list[str] = []
    for token in words:
        if re.match(r"\b\w", token):
            word_seen += 1
        if word_seen > maximum:
            break
        kept.append(token)
    trimmed = " ".join(kept)
    trimmed = re.sub(r"\s+([.,;:!?])", r"\1", trimmed).strip()
    return trimmed.rstrip(" ,;:") + "." if trimmed and trimmed[-1] not in ".!?" else trimmed


def _trim_to_sentence_boundary(text: str, maximum: int) -> str:
    if word_count(text) <= maximum:
        return text.strip()
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
    kept: list[str] = []
    for sentence in sentences:
        candidate = " ".join([*kept, sentence]).strip()
        if word_count(candidate) > maximum:
            break
        kept.append(sentence)
    if kept:
        return " ".join(kept)
    return _trim_words(text, maximum)


def _trim_three_thing(item: str, maximum: int = 80) -> str:
    if word_count(item) <= maximum:
        return _normalize_market_text_spacing(item)
    match = re.search(r"\bSo what:\s*", item, flags=re.IGNORECASE)
    if not match:
        return _normalize_market_text_spacing(_trim_to_sentence_boundary(item, maximum))
    main = item[: match.start()].strip()
    implication = item[match.end() :].strip()
    implication_limit = min(24, max(12, maximum // 3))
    trimmed_implication = _trim_to_sentence_boundary(implication, implication_limit)
    so_what_words = word_count(f"So what: {trimmed_implication}")
    main_limit = max(20, maximum - so_what_words)
    return _normalize_market_text_spacing(f"{_trim_to_sentence_boundary(main, main_limit)} So what: {trimmed_implication}")


def _normalize_market_text_spacing(text: str) -> str:
    normalized = re.sub(r"\b(USD|EUR)\s*/\s*(JPY|USD)\b", r"\1/\2", text)
    normalized = re.sub(r"(?<=\d)\.\s+(?=\d)", ".", normalized)
    normalized = re.sub(r"(?<=\d)\s+%", "%", normalized)
    return normalized


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


def _strip_embedded_theme_impact(summary: str) -> str:
    return re.split(r"\s+So what:\s*", summary, maxsplit=1, flags=re.IGNORECASE)[0].strip()


def _strip_theme_source_mechanics(summary: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", summary)
    banned_fragments = (
        "selector picked",
        "selected it because",
        "selected because",
        "this is relevant",
        "source mechanics",
    )
    kept = [sentence for sentence in sentences if not any(fragment in sentence.lower() for fragment in banned_fragments)]
    return " ".join(kept).strip()


def _rewrite_common_theme_openers(summary: str) -> str:
    rewritten = re.sub(r"\bthis article explores\b", "This article shows", summary, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bthis piece explores\b", "This piece argues", rewritten, flags=re.IGNORECASE)
    return rewritten


def _reject_generic_theme_language(summary: str, idx: int) -> None:
    lowered = summary.lower()
    banned_phrases = (
        "the article explores",
        "this article explores",
        "this article investigates",
        "this article posits",
        "this piece examines",
        "this piece explores",
        "this analysis explores",
        "this analysis examines",
        "this analysis posits",
        "it posits",
        "posits",
    )
    for phrase in banned_phrases:
        if phrase in lowered:
            raise ValueError(f"theme_radar summary {idx} uses generic phrasing: {phrase}")


def _reject_portfolio_logic_errors(text: str, label: str) -> None:
    lowered = text.lower()
    if "dollar strength" in lowered and "risk to our long usd/jpy" in lowered:
        raise ValueError(f"{label} incorrectly treats dollar strength itself as a risk to long USD/JPY")
    if "stronger dollar" in lowered and "risk to our long usd/jpy" in lowered:
        raise ValueError(f"{label} incorrectly treats stronger dollar itself as a risk to long USD/JPY")
    if "carry advantage" in lowered and re.search(r"\bjapan(?:ese)?(?:\s+10y)?\s+yields?\b", lowered):
        raise ValueError(f"{label} must treat higher Japan yields as a USD/JPY spread risk, not generic carry support")


def _reject_unsupported_market_claims(text: str, label: str) -> None:
    lowered = text.lower()
    banned_phrases = (
        "chart",
        "chart caption",
        "record high",
        "record highs",
        "market is increasingly pricing",
        "market pricing",
        "pricing in",
        "priced in",
        "narrowing us-japan",
        "narrowing the us-japan",
        "narrowing yield spread",
        "narrowing spread",
        "narrow the us-japan",
        "narrow the yield spread",
        "narrow the spread",
        "narrows the spread",
        "narrowing the spread",
        "us-japan spread",
        "widen the spread",
        "widens the spread",
        "widening the spread",
        "opened softer",
        "opened lower",
        "opened firmer",
        "opened higher",
        "real rates",
        "real-rate",
        "change flat at",
        "changed flat at",
        "safe-haven",
        "crowded positioning",
        "yen shorts",
        "carry trade",
        "fed remains hawkish",
        "hawkish relative",
        "boj remains dovish",
    )
    for phrase in banned_phrases:
        if phrase in lowered:
            raise ValueError(f"{label} uses unsupported market-positioning language: {phrase}")


def _market_aliases(asset: str) -> tuple[str, ...]:
    aliases = {
        "S&P 500": ("s&p 500", "s&p", "spx"),
        "Euro Stoxx 50": ("euro stoxx 50", "stoxx 50"),
        "US 10Y yield": ("us 10y", "treasury yield", "treasury yields", "us yield", "us yields"),
        "Japan 10Y yield": ("japan 10y", "japan yield", "japan yields", "jgb yield", "jgb yields", "japanese yield", "japanese yields"),
        "DXY": ("dxy", "dollar index"),
        "EUR/USD": ("eur/usd",),
        "USD/JPY": ("usd/jpy",),
        "Gold": ("gold",),
        "WTI oil": ("wti oil", "wti"),
        "BTC": ("btc", "bitcoin"),
    }
    return aliases.get(asset, (asset.lower(),))


def _parse_change(change: str) -> tuple[str, float] | None:
    normalized = change.lower().replace(" ", "")
    if normalized.endswith("bp"):
        try:
            return ("bp", abs(float(normalized.removesuffix("bp"))))
        except ValueError:
            return None
    if normalized.endswith("%"):
        try:
            return ("pct", abs(float(normalized.removesuffix("%"))))
        except ValueError:
            return None
    return None


def _nearby_change_numbers(text: str, alias: str, kind: str) -> list[float]:
    lowered = text.lower()
    alias_pattern = rf"\b{re.escape(alias)}\b"
    number_pattern = r"(?<![\d.])(?P<num>[+-]?\d+(?:\.\d+)?)\s*%" if kind == "pct" else r"(?<![\d.])(?P<num>[+-]?\d+(?:\.\d+)?)\s*bp\b"
    movement_pattern = re.compile(
        r"\b(up|down|rose|rise|rises|rising|fell|fall|falls|falling|gained|gain|gains|"
        r"lost|lose|loses|dropped|drop|drops|declined|decline|declines|increased|"
        r"increase|increases|decreased|decrease|decreases|moved|move|moves|"
        r"appreciated|appreciate|appreciates|weakened|weaken|weakens|"
        r"strengthened|strengthen|strengthens|change|changed)\b"
    )
    values: list[float] = []
    after_pattern = re.compile(rf"{alias_pattern}(?P<between>.{{0,35}}?){number_pattern}", re.IGNORECASE)
    for match in after_pattern.finditer(text):
        if movement_pattern.search(match.group("between").lower()):
            values.append(abs(float(match.group("num"))))
    return values


def _reject_mismatched_market_numbers(text: str, rows: list[MarketRow], label: str) -> None:
    for row in rows:
        parsed = _parse_change(row.change)
        if parsed is None:
            continue
        kind, expected = parsed
        candidates: list[float] = []
        for alias in _market_aliases(row.asset):
            candidates.extend(_nearby_change_numbers(text, alias, kind))
        if candidates and not any(abs(value - expected) <= 0.05 for value in candidates):
            unit = "%" if kind == "pct" else " bp"
            seen = ", ".join(f"{value:g}{unit}" for value in sorted(set(candidates)))
            raise ValueError(
                f"{label} appears to attach {seen} to {row.asset}, "
                f"but the dashboard row change is {row.change}"
            )


def _require_first_item_supports_chart(three_things: list[str]) -> None:
    first = three_things[0].lower()
    if not any(term in first for term in ("usd/jpy", "yen", "japan", "intervention")):
        raise ValueError("three_things item 1 must be the USD/JPY chart-support item")


def build_narrative_prompt(data: BriefData) -> str:
    facts = {
        "market_dashboard": [asdict(row) for row in data.market_rows],
        "dashboard_notes": data.dashboard_notes,
        "calendar": [asdict(event) for event in data.calendar],
        "theme_inputs": [asdict(item) for item in data.theme_radar],
        "assumptions": data.assumptions,
    }

    return (
        "You are writing a Daily Macro Brief for a time-poor macro portfolio manager.\n"
        "Use only the facts below. Do not invent market numbers, source names, links, or positions.\n"
        "If you mention an asset's percentage or bp move, copy that asset's Change value exactly from the market dashboard.\n"
        "Do not move a number from one dashboard row to another.\n"
        "Do not add generic risk factors unless they appear in the facts.\n"
        "Do not claim market pricing, safe-haven flows, crowded positioning, yen shorts, carry trades, or central-bank stances unless those facts appear below.\n"
        "Do not say the US-Japan spread narrowed or widened unless the facts provide a calculated spread; mention the US and Japan yield moves separately.\n"
        "Do not say markets opened higher/lower/softer/firmer unless the facts explicitly provide opening data; use closed lower, traded lower, or were softer.\n"
        "Do not mention real rates unless the facts provide real-yield data; use US yields or rates instead.\n"
        "Do not describe a percentage change as being 'at' a price; say the asset closed at the price and changed by the dashboard Change value.\n"
        "Do not mention JSON field names, charts, figures, prompts, or source mechanics in the brief; describe the underlying market risk directly.\n"
        "Do not use record-high or historical-extreme language unless the facts explicitly provide that history; use 'elevated' if that is all the facts support.\n"
        "Keep the tone concise, investment-oriented, and opinionated.\n"
        "Write like a PM-facing morning note: catalyst first, portfolio read-through second, no filler.\n\n"
        "Portfolio semantics:\n"
        "- A long USD/JPY position benefits when USD/JPY rises, but is hurt by intervention or yen-strength reversal risk.\n"
        "- Do not say dollar strength itself is a risk to long USD/JPY; the risk is intervention, yen reversal, or position crowding after a large rise.\n"
        "- Rising Japan 10Y yields are not automatically supportive for long USD/JPY; compare them with the US yield move and do not infer the trade direction from Japan yields alone.\n"
        "- Do not say higher Japanese yields reinforce USD/JPY carry unless the facts explicitly provide a carry or spread calculation.\n"
        "- A gold overweight benefits when gold rises, but is pressured by higher US yields/rates or dollar strength.\n"
        "- EM debt exposure is usually pressured by higher US yields, stronger dollar funding stress, or weaker China demand.\n\n"
        "Return only valid JSON with this exact shape:\n"
        "{\n"
        '  "three_things": ["string", "string", "string"],\n'
        '  "theme_radar": [\n'
        '    {"title": "string", "source": "string", "link": "string", "summary": "string", "book_impact": "string"}\n'
        "  ],\n"
        '  "contrarian_corner": "string"\n'
        "}\n\n"
        "Constraints:\n"
        "- Each item in three_things should target 70 words or fewer and must be 80 words or fewer; include a clear 'So what:' clause tied to the assumed book.\n"
        "- The first item in three_things must be the USD/JPY or intervention-risk item.\n"
        "- theme_radar must contain 1-3 items and reuse the provided title, source, and link values.\n"
        "- Each theme_radar summary must be 45-100 words, start with the thesis directly, and explain the author's thesis and evidence without generic openers like 'this piece examines', 'this piece explores', 'this article explores', 'this analysis explores', or 'this analysis examines'.\n"
        "- Theme Radar summaries must not mention selector mechanics, ranking, matching keywords, or why the source was picked.\n"
        "- Do not use the word 'posits'. Use 'argues', 'shows', or direct wording instead.\n"
        "- Each book_impact line must start with 'What this means for our book:' and must be specific to that source.\n"
        "- Do not repeat the same book_impact line across Theme Radar items.\n"
        "- contrarian_corner must be 50-100 words, name a simple read or consensus narrative based only on the facts, include one concrete trigger that would challenge it, and avoid exact market move numbers unless essential.\n\n"
        f"Facts:\n{json.dumps(facts, indent=2)}"
    )


def parse_narrative_response(text: str, base_data: BriefData) -> BriefData:
    payload = _extract_json(text)

    three_things = payload.get("three_things")
    if not isinstance(three_things, list) or len(three_things) != 3:
        raise ValueError("Gemini response must include exactly three items in three_things")
    three_things = [_trim_three_thing(_normalize_market_text_spacing(str(item).strip())) for item in three_things]
    _require_first_item_supports_chart(three_things)
    for idx, item in enumerate(three_things, 1):
        if "so what:" not in item.lower():
            raise ValueError(f"three_things item {idx} must include 'So what:'")
        _require_word_max(f"three_things item {idx}", item, 80)
        _reject_portfolio_logic_errors(item, f"three_things item {idx}")
        _reject_unsupported_market_claims(item, f"three_things item {idx}")
        _reject_mismatched_market_numbers(item, base_data.market_rows, f"three_things item {idx}")

    allowed_theme_meta = {(item.title, item.source, item.link): item for item in base_data.theme_radar}
    theme_payload = payload.get("theme_radar")
    if not isinstance(theme_payload, list) or not 1 <= len(theme_payload) <= 3:
        raise ValueError("Gemini response must include 1-3 theme_radar items")

    theme_radar: list[ThemeItem] = []
    seen_book_impacts: set[str] = set()
    for idx, item in enumerate(theme_payload, 1):
        if not isinstance(item, dict):
            raise ValueError(f"theme_radar item {idx} must be an object")
        title = str(item.get("title", "")).strip()
        source = str(item.get("source", "")).strip()
        link = str(item.get("link", "")).strip()
        summary = _normalize_market_text_spacing(
            _rewrite_common_theme_openers(
                _strip_theme_source_mechanics(_strip_embedded_theme_impact(str(item.get("summary", "")).strip()))
            )
        )
        book_impact = _normalize_book_impact(_normalize_market_text_spacing(str(item.get("book_impact", ""))))

        base_theme_item = allowed_theme_meta.get((title, source, link))
        if base_theme_item is None:
            raise ValueError(f"theme_radar item {idx} must reuse an existing title, source, and link")
        _require_word_range(f"theme_radar summary {idx}", summary, 45, 100)
        _reject_generic_theme_language(summary, idx)
        impact_key = book_impact.lower()
        if impact_key in seen_book_impacts:
            raise ValueError("theme_radar book_impact lines must not repeat exactly")
        seen_book_impacts.add(impact_key)
        theme_radar.append(
            ThemeItem(
                title=title,
                source=source,
                link=link,
                summary=summary,
                book_impact=book_impact,
                source_depth=base_theme_item.source_depth,
            )
        )

    contrarian_corner = _normalize_market_text_spacing(str(payload.get("contrarian_corner", "")).strip())
    _require_word_range("contrarian_corner", contrarian_corner, 50, 100)
    _reject_portfolio_logic_errors(contrarian_corner, "contrarian_corner")
    _reject_unsupported_market_claims(contrarian_corner, "contrarian_corner")
    _reject_mismatched_market_numbers(contrarian_corner, base_data.market_rows, "contrarian_corner")

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
    total_usage = TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0, provider="gemini")
    generated_data: BriefData | None = None
    last_validation_error: ValueError | None = None
    last_request_error: RuntimeError | None = None

    max_attempts = 4
    for attempt in range(max_attempts):
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
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
            last_request_error = RuntimeError(f"Gemini request failed: {exc}")
            if attempt == max_attempts - 1:
                break
            continue

        body = response.json()
        candidates = body.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if not text.strip():
            raise RuntimeError("Gemini returned an empty text response")

        usage_metadata = body.get("usageMetadata", {})
        total_usage = TokenUsage(
            input_tokens=total_usage.input_tokens + int(usage_metadata.get("promptTokenCount", 0)),
            output_tokens=total_usage.output_tokens + int(usage_metadata.get("candidatesTokenCount", 0)),
            total_tokens=total_usage.total_tokens + int(usage_metadata.get("totalTokenCount", 0)),
            provider="gemini",
        )

        try:
            generated_data = parse_narrative_response(text, data)
            break
        except ValueError as exc:
            last_validation_error = exc
            if attempt == max_attempts - 1:
                break
            prompt = (
                f"{prompt}\n\n"
                "Validation repair instruction:\n"
                f"The previous JSON failed validation because: {exc}.\n"
                " Keep every three_things item at 70 words or fewer so it safely passes the 80-word limit."
                "Return the full JSON object again. Be especially careful that every theme_radar summary is 45-100 words."
                " Also ensure Theme Radar book_impact lines are source-specific and not repeated."
                " Do not mention selector mechanics, ranking, matching keywords, or why a Theme Radar source was picked."
                " Avoid generic phrases such as 'this piece examines', 'this piece explores', 'this article explores', 'this analysis explores', 'this analysis examines', or 'it posits'."
                " Do not use the word 'posits'."
                " Do not mention chart captions, JSON fields, prompts, source mechanics, market pricing, positioning, or safe-haven flows."
                " If you mention an asset move, copy that asset's dashboard Change value exactly."
                " Do not use record-high or historical-extreme language; use 'elevated' if the facts only show a high current level."
                " Do not say markets opened higher/lower/softer/firmer unless the facts explicitly provide opening data."
                " Do not mention real rates unless the facts provide real-yield data."
                " Do not describe an asset's change as being at a price."
                " Do not say the US-Japan spread narrowed or widened unless the facts provide a calculated spread."
                " Do not frame dollar strength itself as a risk to long USD/JPY; only intervention or yen reversal are risks."
                " In contrarian_corner, avoid exact market move numbers; focus on the competing narrative and the trigger."
            )

    if generated_data is None:
        if last_request_error is not None and last_validation_error is None:
            raise last_request_error
        raise RuntimeError(f"Gemini response failed validation after retries: {last_validation_error}") from last_validation_error

    usage = total_usage
    estimated_cost = estimate_llm_cost_usd("gemini", settings.gemini_model, usage)

    return SynthesisResult(
        data=generated_data,
        token_usage=usage,
        estimated_cost_usd=estimated_cost,
        provider="gemini",
        model=settings.gemini_model,
        prompt_version=PROMPT_VERSION,
    )
