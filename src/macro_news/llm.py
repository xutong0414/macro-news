from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace

import httpx

from .config import Settings
from .costing import TokenUsage, estimate_llm_cost_usd
from .narrative_rules import (
    validate_asset_move_contradictions,
    validate_market_directions,
    validate_market_numbers,
    validate_portfolio_logic,
    validate_unsupported_market_claims,
)
from .sample_data import BriefData, ThemeItem

PROMPT_VERSION = "gemini_narrative_v43"


@dataclass(frozen=True)
class SynthesisResult:
    data: BriefData
    token_usage: TokenUsage
    estimated_cost_usd: float
    provider: str
    model: str
    prompt_version: str
    validation_attempts: int = 1
    validation_repair_count: int = 0
    validation_errors: tuple[str, ...] = ()


class NarrativeValidationFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        validation_errors: tuple[str, ...],
        failed_responses: tuple[str, ...],
        prompt_version: str,
        token_usage: TokenUsage,
    ) -> None:
        super().__init__(message)
        self.validation_errors = validation_errors
        self.failed_responses = failed_responses
        self.prompt_version = prompt_version
        self.token_usage = token_usage


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


def _normalize_three_thing_item(item: object, idx: int) -> str:
    if isinstance(item, dict):
        body = _normalize_market_text_spacing(str(item.get("body", "")).strip())
        so_what = _normalize_market_text_spacing(str(item.get("so_what", "")).strip())
        if not body or not so_what:
            raise ValueError(f"three_things item {idx} must include body and so_what")
        body = re.sub(r"\s*\bSo what:\s*", " ", body, flags=re.IGNORECASE).strip()
        so_what = re.sub(r"^\s*So what:\s*", "", so_what, flags=re.IGNORECASE).strip()
        return _trim_three_thing(f"{body} So what: {so_what}")
    return _trim_three_thing(_normalize_market_text_spacing(str(item).strip()))


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("Gemini response did not contain a JSON object")
    try:
        payload, _end = json.JSONDecoder().raw_decode(cleaned[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini response did not contain a valid JSON object: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Gemini response JSON root must be an object")
    return payload


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
        "portfolio link:",
        "source input",
        "this is relevant",
        "source mechanics",
    )
    kept = [sentence for sentence in sentences if not any(fragment in sentence.lower() for fragment in banned_fragments)]
    return " ".join(kept).strip()


def _rewrite_common_theme_openers(summary: str) -> str:
    rewritten = re.sub(r"\bthis article explores\b", "This article shows", summary, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bthis piece explores\b", "This piece argues", rewritten, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bthis article examines\b", "This article shows", rewritten, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bthis piece examines\b", "This piece shows", rewritten, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bthis analysis examines\b", "The analysis shows", rewritten, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bthis report examines\b", "The report shows", rewritten, flags=re.IGNORECASE)
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


def _require_selected_topic_alignment(three_things: list[str], base_data: BriefData) -> None:
    if len(base_data.topic_candidates) < len(three_things):
        return
    for idx, (item, candidate) in enumerate(zip(three_things, base_data.topic_candidates, strict=False), 1):
        required_terms = candidate.get("required_terms", [])
        if not isinstance(required_terms, list) or not required_terms:
            continue
        lowered = item.lower()
        if not any(str(term).lower() in lowered for term in required_terms):
            title = str(candidate.get("title", f"topic {idx}"))
            raise ValueError(f"three_things item {idx} must clearly address selected topic: {title}")


def _require_contrarian_alignment(contrarian_corner: str, base_data: BriefData) -> None:
    if not base_data.topic_candidates:
        return
    first_topic = base_data.topic_candidates[0]
    required_terms = first_topic.get("required_terms", [])
    if not isinstance(required_terms, list) or not required_terms:
        return
    lowered = contrarian_corner.lower()
    if not any(str(term).lower() in lowered for term in required_terms):
        title = str(first_topic.get("title", "the first selected topic"))
        raise ValueError(f"contrarian_corner must challenge the first selected topic: {title}")


def _prompt_guardrail_summary(topic_candidates: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for idx, candidate in enumerate(topic_candidates, 1):
        guidance = str(candidate.get("narrative_guidance", "")).strip()
        avoid_claims = candidate.get("avoid_claims", [])
        if not guidance and not avoid_claims:
            continue
        title = str(candidate.get("title", f"topic {idx}")).strip()
        lines.append(f"{idx}. {title}")
        if guidance:
            lines.append(f"   Guidance: {guidance}")
        if isinstance(avoid_claims, list) and avoid_claims:
            claims = " ".join(str(claim).strip() for claim in avoid_claims if str(claim).strip())
            if claims:
                lines.append(f"   Avoid: {claims}")
    if not lines:
        return "None."
    return "\n".join(lines)


def build_narrative_prompt(data: BriefData) -> str:
    facts = {
        "market_dashboard": [asdict(row) for row in data.market_rows],
        "dashboard_notes": data.dashboard_notes,
        "calendar": [asdict(event) for event in data.calendar],
        "theme_inputs": [asdict(item) for item in data.theme_radar],
        "selected_topics": data.topic_candidates,
        "selected_chart": {
            "title": data.chart_title,
            "source_label": data.chart_source_label,
            "source_url": data.chart_source_url,
            "caption": data.chart_caption,
        },
        "assumptions": data.assumptions,
    }
    guardrail_summary = _prompt_guardrail_summary(data.topic_candidates)

    return (
        "You are writing a Daily Macro Brief for a time-poor macro portfolio manager.\n"
        "Use only the facts below. Do not invent market numbers, source names, links, or positions.\n"
        "If you mention an asset's percentage or bp move, copy that asset's Change value exactly from the market dashboard.\n"
        "Do not move a number from one dashboard row to another.\n"
        "Do not add generic risk factors unless they appear in the facts.\n"
        "Do not claim market pricing, safe-haven flows, crowded positioning, yen shorts, carry trades, or central-bank stances unless those facts appear below.\n"
        "Do not use the phrases 'pricing in', 'priced in', 'market is pricing', or 'market pricing' in Three Things or Contrarian Corner.\n"
        "Do not say the US-Japan spread narrowed or widened unless the facts provide a calculated spread; mention the US and Japan yield moves separately.\n"
        "Do not say markets opened higher/lower/softer/firmer unless the facts explicitly provide opening data; use closed lower, traded lower, or were softer.\n"
        "Do not mention real rates unless the facts provide real-yield data; use US yields or rates instead.\n"
        "Do not describe a percentage change as being 'at' a price; say the asset closed at the price and changed by the dashboard Change value.\n"
        "Do not mention JSON field names, charts, figures, prompts, or source mechanics in the brief; describe the underlying market risk directly.\n"
        "Do not use record-high or historical-extreme language unless the facts explicitly provide that history; use 'elevated' if that is all the facts support.\n"
        "Keep the tone concise, investment-oriented, and opinionated.\n"
        "Write like a PM-facing morning note: catalyst first, portfolio read-through second, no filler.\n\n"
        "Critical code guardrails, checked before delivery:\n"
        f"{guardrail_summary}\n\n"
        "Topic agenda:\n"
        "- selected_topics is code-ranked before this prompt from market moves, calendar events, Theme Radar/news signals, source/event importance, freshness, and portfolio relevance.\n"
        "- If selected_topics is non-empty, write three_things in exactly that order.\n"
        "- Each item must clearly address the corresponding selected topic and use its evidence.\n"
        "- Each selected topic may include narrative_guidance and avoid_claims. Treat narrative_guidance as code-generated logic guidance, and do not contradict it.\n"
        "- Never make a claim listed in a selected topic's avoid_claims.\n"
        "- Do not force USD/JPY into the first item unless selected_topics puts it first.\n"
        "- selected_chart is code-selected to support the first selected topic; do not mention charts directly in the narrative.\n\n"
        "Contrarian Corner:\n"
        "- If selected_topics is non-empty, write contrarian_corner as the pushback to the first selected topic.\n"
        "- The contrarian view should challenge the simple read from selected_topics[0], not introduce an unrelated topic.\n"
        "- Name the simple read or consensus view, state why that view could be wrong, include one concrete trigger that would make the pushback more plausible, and tie the implication back to the assumed book.\n"
        "- Do not invent a further-reading link; the application renders available links separately.\n\n"
        "Portfolio semantics:\n"
        "- A long USD/JPY position benefits when USD/JPY rises, but is hurt by intervention or yen-strength reversal risk.\n"
        "- Stronger dollar pressure or higher US yields usually support a long USD/JPY position; they are not, by themselves, pressure on the long.\n"
        "- Hawkish Fed expectations or hotter US inflation are not pressure on a long USD/JPY position unless the stated risk is intervention, yen reversal, or crowding after USD/JPY rises.\n"
        "- Hotter-than-expected US inflation usually pushes US yields and the dollar higher; cooler-than-expected inflation usually pushes them lower. Do not invert this direction.\n"
        "- Do not say dollar strength itself is a risk to long USD/JPY; the risk is intervention, yen reversal, or position crowding after a large rise.\n"
        "- Rising Japan 10Y yields are not automatically supportive for long USD/JPY; compare them with the US yield move and do not infer the trade direction from Japan yields alone.\n"
        "- Do not say higher Japanese yields reinforce USD/JPY carry unless the facts explicitly provide a carry or spread calculation.\n"
        "- For ECB event risk, a hawkish ECB surprise is generally euro-supportive and a dovish ECB surprise is generally euro-negative; if the facts do not give the actual outcome, frame it as two-way event risk.\n"
        "- A gold overweight benefits when gold rises, but is pressured by higher US yields/rates or dollar strength.\n"
        "- EM debt exposure is usually pressured by higher US yields, stronger dollar funding stress, or weaker China demand.\n\n"
        "Dashboard direction checks:\n"
        "- If DXY Change is positive, do not say broad dollar pressure eased or dollar funding conditions loosened.\n"
        "- If DXY Change is negative, do not say broad dollar pressure tightened unless other provided facts support that claim.\n"
        "- If oil Change is positive, do not say inflation pressure eased because of oil; if oil Change is negative, do not say oil increased inflation pressure.\n\n"
        "Return only valid JSON with this exact shape:\n"
        "{\n"
        '  "three_things": [\n'
        '    {"body": "string", "so_what": "string"},\n'
        '    {"body": "string", "so_what": "string"},\n'
        '    {"body": "string", "so_what": "string"}\n'
        "  ],\n"
        '  "theme_radar": [\n'
        '    {"title": "string", "source": "string", "link": "string", "summary": "string", "book_impact": "string"}\n'
        "  ],\n"
        '  "contrarian_corner": "string"\n'
        "}\n\n"
        "Constraints:\n"
        "- Each item in three_things must be an object with body and so_what.\n"
        "- Do not write the words 'So what:' inside body or so_what; the application will render that label.\n"
        "- Each rendered three_things item should target 70 words or fewer and must be 80 words or fewer; so_what must be tied to the assumed book.\n"
        "- If selected_topics is provided, each three_things item must follow the matching selected topic in order.\n"
        "- theme_radar must contain 1-3 items and reuse the provided title, source, and link values.\n"
        "- Each theme_radar summary must be 45-100 words, start with the thesis directly, and explain the author's thesis and evidence without generic openers like 'this piece examines', 'this piece explores', 'this article explores', 'this analysis explores', or 'this analysis examines'.\n"
        "- Theme Radar summaries must not mention selector mechanics, ranking, matching keywords, or why the source was picked.\n"
        "- Do not use the word 'posits'. Use 'argues', 'shows', or direct wording instead.\n"
        "- Each book_impact line must start with 'What this means for our book:' and must be specific to that source.\n"
        "- Do not repeat the same book_impact line across Theme Radar items.\n"
        "- contrarian_corner must be 50-100 words, name a simple read or consensus narrative based only on the facts, challenge the first selected topic when selected_topics exists, explain why that read could be wrong, include one concrete trigger, tie the implication back to the book, and avoid exact market move numbers unless essential.\n\n"
        f"Facts:\n{json.dumps(facts, indent=2)}"
    )


def parse_narrative_response(text: str, base_data: BriefData) -> BriefData:
    payload = _extract_json(text)

    three_things = payload.get("three_things")
    if not isinstance(three_things, list) or len(three_things) != 3:
        raise ValueError("Gemini response must include exactly three items in three_things")
    three_things = [_normalize_three_thing_item(item, idx) for idx, item in enumerate(three_things, 1)]
    _require_selected_topic_alignment(three_things, base_data)
    for idx, item in enumerate(three_things, 1):
        if "so what:" not in item.lower():
            raise ValueError(f"three_things item {idx} must include 'So what:'")
        _require_word_max(f"three_things item {idx}", item, 80)
        validate_portfolio_logic(item, f"three_things item {idx}")
        validate_unsupported_market_claims(item, f"three_things item {idx}")
        validate_market_numbers(item, base_data.market_rows, f"three_things item {idx}")
        validate_market_directions(item, base_data.market_rows, f"three_things item {idx}")
        validate_asset_move_contradictions(item, base_data.market_rows, f"three_things item {idx}")

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
    validate_portfolio_logic(contrarian_corner, "contrarian_corner")
    validate_unsupported_market_claims(contrarian_corner, "contrarian_corner")
    validate_market_numbers(contrarian_corner, base_data.market_rows, "contrarian_corner")
    validate_market_directions(contrarian_corner, base_data.market_rows, "contrarian_corner")
    validate_asset_move_contradictions(contrarian_corner, base_data.market_rows, "contrarian_corner")
    _require_contrarian_alignment(contrarian_corner, base_data)

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
    validation_errors: list[str] = []
    failed_responses: list[str] = []
    attempts_made = 0

    max_attempts = 4
    for attempt in range(max_attempts):
        attempts_made = attempt + 1
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
            validation_errors.append(str(exc))
            failed_responses.append(text)
            if attempt == max_attempts - 1:
                break
            prompt = (
                f"{prompt}\n\n"
                "Validation repair instruction:\n"
                f"The previous JSON failed validation because: {exc}.\n"
                " Return each three_things item as an object with body and so_what."
                " Do not write the literal label 'So what:' inside either field; the application renders that label."
                " Keep every rendered three_things item at 70 words or fewer so it safely passes the 80-word limit."
                " Follow selected_topics exactly in order when selected_topics is provided."
                " Make contrarian_corner challenge the first selected topic when selected_topics is provided."
                " Return the full JSON object again. Be especially careful that every theme_radar summary is 45-100 words."
                " Also ensure Theme Radar book_impact lines are source-specific and not repeated."
                " Do not mention selector mechanics, ranking, matching keywords, or why a Theme Radar source was picked."
                " Use each selected topic's narrative_guidance and avoid_claims as binding guardrails."
                " Avoid generic phrases such as 'this piece examines', 'this piece explores', 'this article explores', 'this analysis explores', 'this analysis examines', or 'it posits'."
                " Do not use the word 'posits'."
                " Do not use the phrases 'pricing in', 'priced in', 'market is pricing', or 'market pricing'."
                " Do not mention chart captions, JSON fields, prompts, source mechanics, market pricing, positioning, or safe-haven flows."
                " If you mention an asset move, copy that asset's dashboard Change value exactly."
                " Do not use record-high or historical-extreme language; use 'elevated' if the facts only show a high current level."
                " Do not say markets opened higher/lower/softer/firmer unless the facts explicitly provide opening data."
                " Do not mention real rates unless the facts provide real-yield data."
                " Do not describe an asset's change as being at a price."
                " Do not say the US-Japan spread narrowed or widened unless the facts provide a calculated spread."
                " Do not frame dollar strength itself as a risk to long USD/JPY; only intervention or yen reversal are risks."
                " Do not frame dollar support or higher US yields as pressure on a long USD/JPY position."
                " Do not frame hawkish Fed expectations as pressure on a long USD/JPY position unless the risk is intervention or yen reversal after USD/JPY rises."
                " Do not say hotter US inflation lowers US yields or cooler US inflation raises US yields."
                " Do not say a dovish ECB surprise supports the euro, and do not say a hawkish ECB surprise weakens the euro."
                " If DXY Change is positive, do not say broad dollar pressure eased or dollar funding conditions loosened."
                " If DXY Change is negative, do not say broad dollar pressure tightened unless another provided fact supports it."
                " If oil Change is positive, do not say inflation pressure eased because of oil; if oil Change is negative, do not say oil increased inflation pressure."
                " In contrarian_corner, avoid exact market move numbers; focus on the competing narrative and the trigger."
            )

    if generated_data is None:
        if last_request_error is not None and last_validation_error is None:
            raise last_request_error
        message = f"Gemini response failed validation after retries: {last_validation_error}"
        raise NarrativeValidationFailure(
            message,
            validation_errors=tuple(validation_errors),
            failed_responses=tuple(failed_responses),
            prompt_version=PROMPT_VERSION,
            token_usage=total_usage,
        ) from last_validation_error

    usage = total_usage
    estimated_cost = estimate_llm_cost_usd("gemini", settings.gemini_model, usage)

    return SynthesisResult(
        data=generated_data,
        token_usage=usage,
        estimated_cost_usd=estimated_cost,
        provider="gemini",
        model=settings.gemini_model,
        prompt_version=PROMPT_VERSION,
        validation_attempts=attempts_made,
        validation_repair_count=len(validation_errors),
        validation_errors=tuple(validation_errors),
    )
