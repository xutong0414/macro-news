from __future__ import annotations

import re
from dataclasses import dataclass

from .sample_data import MarketRow


@dataclass(frozen=True)
class CombinedTextRule:
    name: str
    patterns: tuple[str, ...]
    message: str


PORTFOLIO_RULES = (
    CombinedTextRule(
        name="usd_jpy_long_dollar_strength",
        patterns=(r"\bdollar strength\b", r"\brisk to our long usd/jpy\b"),
        message="incorrectly treats dollar strength itself as a risk to long USD/JPY",
    ),
    CombinedTextRule(
        name="usd_jpy_long_stronger_dollar",
        patterns=(r"\bstronger dollar\b", r"\brisk to our long usd/jpy\b"),
        message="incorrectly treats stronger dollar itself as a risk to long USD/JPY",
    ),
    CombinedTextRule(
        name="usd_jpy_long_dollar_support_pressure",
        patterns=(
            r"\b(support|strengthen|stronger)\b.{0,25}\bdollar\b",
            r"\b(pressure|challenge|hurt|risk)\b.{0,35}\b(long usd/jpy|usd/jpy long|usd/jpy position)\b",
        ),
        message="incorrectly treats dollar support as pressure on long USD/JPY",
    ),
    CombinedTextRule(
        name="usd_jpy_long_us_rates_pressure",
        patterns=(
            r"\b(hawkish fed|higher us yields|higher us rates|hot us inflation|elevated inflation)\b",
            r"\b(pressure|challenge|hurt|risk)\b.{0,35}\b(long usd/jpy|usd/jpy long|usd/jpy position)\b",
        ),
        message="incorrectly treats hawkish US rates pressure as pressure on long USD/JPY",
    ),
    CombinedTextRule(
        name="japan_yield_carry_error",
        patterns=(r"\bcarry advantage\b", r"\bjapan(?:ese)?(?:\s+10y)?\s+yields?\b"),
        message="must treat higher Japan yields as a USD/JPY spread risk, not generic carry support",
    ),
    CombinedTextRule(
        name="ecb_hawkish_euro_negative",
        patterns=(r"\bhawkish\b", r"\becb\b", r"\b(pressure|weaken|weigh on|hurt)\b.{0,25}\b(eur/usd|euro|eur)\b"),
        message="incorrectly treats a hawkish ECB surprise as euro-negative",
    ),
    CombinedTextRule(
        name="ecb_dovish_euro_positive",
        patterns=(r"\bdovish\b", r"\becb\b", r"\b(eur/usd|euro|eur)\b.{0,20}\b(strength|stronger)\b|\beuro strength\b"),
        message="incorrectly treats a dovish ECB surprise as euro-positive",
    ),
    CombinedTextRule(
        name="hotter_inflation_lower_yields",
        patterns=(
            r"\b(hotter|hot|stronger|higher)-?than-expected\b.{0,80}\b(us 10y yields?|treasury yields?|yields?)\b",
            r"\b(lower|down|fall|fell|decline|soften)\b",
        ),
        message="incorrectly treats hotter inflation as yield-negative",
    ),
    CombinedTextRule(
        name="cooler_inflation_higher_yields",
        patterns=(
            r"\b(cooler|weaker|lower)-?than-expected\b.{0,80}\b(us 10y yields?|treasury yields?|yields?)\b",
            r"\b(higher|up|rise|rose|increase|firm)\b",
        ),
        message="incorrectly treats cooler inflation as yield-positive",
    ),
)

UNSUPPORTED_MARKET_CLAIMS = (
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


def _matches_all(text: str, patterns: tuple[str, ...]) -> bool:
    return all(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def validate_portfolio_logic(text: str, label: str) -> None:
    lowered = text.lower()
    for rule in PORTFOLIO_RULES:
        if _matches_all(lowered, rule.patterns):
            raise ValueError(f"{label} violates {rule.name}: {rule.message}")


def validate_unsupported_market_claims(text: str, label: str) -> None:
    lowered = text.lower()
    for phrase in UNSUPPORTED_MARKET_CLAIMS:
        if phrase in lowered:
            raise ValueError(f"{label} violates unsupported_market_claim: uses unsupported market-positioning language: {phrase}")


def _market_aliases(asset: str) -> tuple[str, ...]:
    aliases = {
        "S&P 500": ("s&p 500", "s&p", "spx"),
        "Euro Stoxx 50": ("euro stoxx 50", "stoxx 50"),
        "US 10Y yield": ("us 10y", "treasury yield", "treasury yields", "us yield", "us yields"),
        "Japan 10Y yield": (
            "japan 10y",
            "japan yield",
            "japan yields",
            "jgb yield",
            "jgb yields",
            "japanese yield",
            "japanese yields",
        ),
        "DXY": ("dxy", "dollar index"),
        "EUR/USD": ("eur/usd",),
        "USD/JPY": ("usd/jpy",),
        "Gold": ("gold",),
        "Brent oil": ("brent oil", "brent"),
        "WTI oil": ("wti oil", "wti"),
        "China internet / tech basket": ("china internet", "china tech", "kweb"),
        "VIX": ("vix", "volatility"),
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


def _change_direction(change: str) -> str:
    stripped = change.strip()
    if stripped.startswith("+"):
        return "up"
    if stripped.startswith("-"):
        return "down"
    return "flat"


def _nearby_change_numbers(text: str, alias: str, kind: str) -> list[float]:
    alias_pattern = rf"\b{re.escape(alias)}\b"
    number_pattern = (
        r"(?<![\d.])(?P<num>[+-]?\d+(?:\.\d+)?)\s*%"
        if kind == "pct"
        else r"(?<![\d.])(?P<num>[+-]?\d+(?:\.\d+)?)\s*bp\b"
    )
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


def validate_market_numbers(text: str, rows: list[MarketRow], label: str) -> None:
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
                f"{label} violates market_number_consistency: appears to attach {seen} to {row.asset}, "
                f"but the dashboard row change is {row.change}"
            )


def validate_market_directions(text: str, rows: list[MarketRow], label: str) -> None:
    lowered = text.lower()
    row_by_asset = {row.asset: row for row in rows}
    us_10y = row_by_asset.get("US 10Y yield")
    if us_10y and us_10y.change.strip().startswith("-"):
        rising_phrases = (
            "rising us yields",
            "higher us yields",
            "us yields rose",
            "us yields are rising",
            "rising treasury yields",
            "higher treasury yields",
            "treasury yields rose",
            "rising us rates",
            "higher us rates",
        )
        if any(phrase in lowered for phrase in rising_phrases):
            raise ValueError(f"{label} violates market_direction_consistency: says US yields rose while the dashboard shows {us_10y.change}")
    if us_10y and us_10y.change.strip().startswith("+"):
        falling_phrases = (
            "falling us yields",
            "lower us yields",
            "us yields fell",
            "us yields are falling",
            "falling treasury yields",
            "lower treasury yields",
            "treasury yields fell",
            "falling us rates",
            "lower us rates",
        )
        if any(phrase in lowered for phrase in falling_phrases):
            raise ValueError(f"{label} violates market_direction_consistency: says US yields fell while the dashboard shows {us_10y.change}")


def _has_row_direction(rows: list[MarketRow], assets: tuple[str, ...], direction: str) -> bool:
    return any(row.asset in assets and _change_direction(row.change) == direction for row in rows)


def validate_asset_move_contradictions(text: str, rows: list[MarketRow], label: str) -> None:
    lowered = text.lower()
    oil_assets = ("Brent oil", "WTI oil")
    if _has_row_direction(rows, oil_assets, "up") and (
        re.search(r"\boil\b.{0,50}\b(ease|eases|eased|cool|cools|cooled)\b.{0,40}\binflation", lowered)
        or re.search(r"\binflation (pressure|risk|impulse)\b.{0,40}\b(ease|eases|eased|cool|cools|cooled|disinflation)", lowered)
    ):
        raise ValueError(f"{label} violates oil_inflation_direction: oil is up but the narrative says inflation pressure eased")
    if _has_row_direction(rows, oil_assets, "down") and re.search(
        r"\boil\b.{0,80}\b(add|adds|added|adding|increase|increases|increased|rebuild|rebuilds|rebuilding|raise|raises|raising)\b.{0,40}\binflation",
        lowered,
    ):
        raise ValueError(f"{label} violates oil_inflation_direction: oil is down but the narrative says inflation pressure increased")

    if _has_row_direction(rows, ("Gold",), "up") and re.search(r"\bgold\b.{0,80}\b(hurt|hurts|pressure|pressures|challenge|challenges|biting)\b.{0,40}\b(overweight|book)", lowered):
        raise ValueError(f"{label} violates gold_position_direction: gold is up but the narrative says the gold overweight is hurt")
    if _has_row_direction(rows, ("Gold",), "down") and re.search(r"\bgold\b.{0,80}\b(help|helps|support|supports|benefit|benefits|cushion)\b.{0,40}\b(overweight|book)", lowered):
        raise ValueError(f"{label} violates gold_position_direction: gold is down but the narrative says the gold overweight is helped")

    underweight_equity = r"\bunderweight\b.{0,45}\b(s&p|s & p|spx|equity|equities)"
    supportive_terms = r"(tailwind|benefit|benefits|help|helps|support|supports|positive)"
    direct_underweight_support = r"(benefits|benefited|is supported|gets support|is helped|tailwind)"
    if _has_row_direction(rows, ("S&P 500",), "up") and (
        re.search(rf"\b{supportive_terms}\b.{{0,90}}{underweight_equity}", lowered)
        or re.search(rf"{underweight_equity}.{{0,45}}\b(position|book)\b.{{0,25}}\b{direct_underweight_support}\b", lowered)
    ):
        raise ValueError(f"{label} violates equity_underweight_direction: S&P 500 is up but the narrative says the underweight position benefits")
    pressure_terms = r"(headwind|hurt|hurts|pressure|pressures|challenge|challenges|negative)"
    if _has_row_direction(rows, ("S&P 500",), "down") and (
        re.search(rf"\b{pressure_terms}\b.{{0,90}}{underweight_equity}", lowered)
        or re.search(rf"{underweight_equity}.{{0,90}}\b{pressure_terms}\b", lowered)
    ):
        raise ValueError(f"{label} violates equity_underweight_direction: S&P 500 is down but the narrative says the underweight position is hurt")

    if _has_row_direction(rows, ("DXY",), "up") and (
        re.search(
            r"\bdollar\s+(funding\s+|financing\s+)?(pressure|conditions|stress)\b.{0,50}\b(ease|eases|eased|soften|softens|softened|loosen|loosens|loosened|relief|less pressure)",
            lowered,
        )
        or re.search(
            r"\b(ease|eases|eased|soften|softens|softened|loosen|loosens|loosened|relief|less pressure)\b.{0,50}\bdollar\s+(funding\s+|financing\s+)?(pressure|conditions|stress)\b",
            lowered,
        )
        or re.search(r"\bdxy\s+(is\s+|was\s+|has\s+|had\s+)?(easing|eases|eased|softening|softens|softened|fell|falls|falling|lower)\b", lowered)
    ):
        raise ValueError(f"{label} violates dollar_direction: DXY is up but the narrative says dollar pressure eased")
    if _has_row_direction(rows, ("DXY",), "down") and (
        re.search(
            r"\bdollar\s+(funding\s+|financing\s+)?(pressure|conditions|stress)\b.{0,50}\b(tighten|tightens|tightened|firmer|higher|stress|stressed)",
            lowered,
        )
        or re.search(
            r"\b(tighten|tightens|tightened|firmer|higher|stress|stressed)\b.{0,50}\bdollar\s+(funding\s+|financing\s+)?(pressure|conditions|stress)\b",
            lowered,
        )
        or re.search(r"\bdxy\s+(is\s+|was\s+|has\s+|had\s+)?(rising|rises|rose|firmer|higher|strengthening|strengthens|strengthened)\b", lowered)
    ):
        raise ValueError(f"{label} violates dollar_direction: DXY is down but the narrative says dollar pressure tightened")

    if _has_row_direction(rows, ("VIX",), "up") and re.search(r"\b(vix|volatility|hedging)\b.{0,80}\b(fade|fades|faded|calm|calmer|relief|eased)\b", lowered):
        raise ValueError(f"{label} violates volatility_direction: VIX is up but the narrative says hedging stress faded")
    if _has_row_direction(rows, ("VIX",), "down") and (
        re.search(r"\b(vix|volatility)\b.{0,80}\b(rise|rises|rose|rising|increase|increases|increased|higher|firmer)\b", lowered)
        or re.search(
            r"\b(volatility|hedging|defensive)\s+(stress|demand)\b.{0,40}\b(rise|rises|rose|rising|increase|increases|increased|higher|firmer)\b",
            lowered,
        )
        or re.search(
            r"\b(rise|rises|rose|rising|increase|increases|increased|higher|firmer)\b.{0,40}\b(volatility|hedging|defensive)\s+(stress|demand)\b",
            lowered,
        )
    ):
        raise ValueError(f"{label} violates volatility_direction: VIX is down but the narrative says defensive stress increased")

    macro_headwind = r"(higher us yields|higher treasury yields|stronger dollar|dollar strength)"
    helpful_terms = r"(help|helps|support|supports|benefit|benefits|relief|constructive)"
    if re.search(
        rf"\bem debt\b.{{0,80}}\b(helped|supported|benefited)\b.{{0,25}}\b(by|from|because of|due to|on)\b.{{0,30}}\b{macro_headwind}\b",
        lowered,
    ) or re.search(
        rf"\b{macro_headwind}\b.{{0,80}}\b{helpful_terms}\b.{{0,50}}\bem debt\b",
        lowered,
    ):
        raise ValueError(f"{label} violates em_debt_macro_direction: EM debt is described as helped by higher US yields or stronger dollar")
