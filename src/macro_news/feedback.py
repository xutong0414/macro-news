from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FeedbackAdjustment:
    item: str
    section: str
    usefulness: int
    adjustment: float
    comment: str


def _clean_text(value: str) -> str:
    return re.sub(r"[^a-z0-9/]+", " ", value.lower()).strip()


def _score_from_usefulness(value: str, comment: str) -> tuple[int, float]:
    try:
        usefulness = int(str(value).strip())
    except (TypeError, ValueError):
        usefulness = 3
    usefulness = max(1, min(5, usefulness))
    adjustment = {
        1: -1.0,
        2: -0.5,
        3: 0.0,
        4: 0.35,
        5: 0.7,
    }[usefulness]
    lowered_comment = comment.lower()
    if any(term in lowered_comment for term in ("avoid", "too generic", "not useful", "irrelevant")):
        adjustment = min(adjustment, -0.5)
    if any(term in lowered_comment for term in ("useful", "directly relevant", "keep", "concrete")) and adjustment >= 0:
        adjustment = max(adjustment, 0.35)
    return usefulness, adjustment


def read_feedback_adjustments(path: Path) -> list[FeedbackAdjustment]:
    if not path.exists():
        return []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return []

    adjustments: list[FeedbackAdjustment] = []
    for row in rows:
        item = str(row.get("item", "")).strip()
        if not item:
            continue
        section = str(row.get("section", "")).strip()
        comment = str(row.get("comment", "")).strip()
        usefulness, adjustment = _score_from_usefulness(str(row.get("usefulness", "")), comment)
        if adjustment == 0:
            continue
        adjustments.append(
            FeedbackAdjustment(
                item=item,
                section=section,
                usefulness=usefulness,
                adjustment=adjustment,
                comment=comment,
            )
        )
    return adjustments


def feedback_adjustment_for_text(text: str, adjustments: list[FeedbackAdjustment]) -> tuple[float, tuple[str, ...]]:
    if not adjustments:
        return 0.0, ()
    cleaned_text = _clean_text(text)
    total = 0.0
    matched: list[str] = []
    for adjustment in adjustments:
        cleaned_item = _clean_text(adjustment.item)
        if not cleaned_item:
            continue
        item_tokens = [token for token in cleaned_item.split() if len(token) >= 3]
        direct_match = cleaned_item in cleaned_text
        token_match = bool(item_tokens) and sum(token in cleaned_text for token in item_tokens) >= min(2, len(item_tokens))
        if direct_match or token_match:
            total += adjustment.adjustment
            matched.append(adjustment.item)
    return total, tuple(dict.fromkeys(matched))
