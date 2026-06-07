from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from .sample_data import BriefData


@dataclass(frozen=True)
class PositionEntry:
    effective_date: date
    asset: str
    position: str
    exposure: str
    quantity: str
    unit: str
    notes: str


def _clean(value: object) -> str:
    return str(value or "").strip()


def read_position_entries(path: Path) -> list[PositionEntry]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        entries: list[PositionEntry] = []
        for row in reader:
            raw_date = _clean(row.get("effective_date"))
            asset = _clean(row.get("asset"))
            if not raw_date or not asset:
                continue
            entries.append(
                PositionEntry(
                    effective_date=date.fromisoformat(raw_date),
                    asset=asset,
                    position=_clean(row.get("position")),
                    exposure=_clean(row.get("exposure")),
                    quantity=_clean(row.get("quantity")),
                    unit=_clean(row.get("unit")),
                    notes=_clean(row.get("notes")),
                )
            )
    return entries


def active_positions(entries: list[PositionEntry], run_date: date) -> list[PositionEntry]:
    latest_by_asset: dict[str, PositionEntry] = {}
    for entry in sorted(entries, key=lambda item: (item.asset.lower(), item.effective_date)):
        if entry.effective_date > run_date:
            continue
        latest_by_asset[entry.asset] = entry
    active: list[PositionEntry] = []
    for entry in latest_by_asset.values():
        if entry.position.lower() in {"", "flat", "closed", "none", "0"}:
            continue
        active.append(entry)
    return sorted(active, key=lambda item: item.asset.lower())


def _position_phrase(entry: PositionEntry) -> str:
    details = [entry.position]
    if entry.exposure:
        details.append(f"exposure={entry.exposure}")
    if entry.quantity:
        quantity = f"{entry.quantity} {entry.unit}".strip()
        details.append(f"quantity={quantity}")
    if entry.notes:
        details.append(entry.notes)
    return f"{entry.asset}: " + "; ".join(details)


def apply_portfolio_assumptions(data: BriefData, *, run_date: date, path: Path) -> BriefData:
    entries = read_position_entries(path)
    if not entries:
        return data
    positions = active_positions(entries, run_date)
    if not positions:
        assumptions = [
            f"Portfolio file {path} has no active positions as of {run_date.isoformat()}.",
            "Position carry-forward rule: if no row is entered for a run date, the latest prior row for that asset remains active.",
        ]
    else:
        assumptions = [
            f"Portfolio file: {path}. Active positions as of {run_date.isoformat()} use the latest effective-date row at or before the run date.",
            "Position carry-forward rule: if no row is entered for a run date, the latest prior row for that asset remains active.",
            *[_position_phrase(entry) for entry in positions],
        ]
    return replace(
        data,
        assumptions=[
            *assumptions,
            *[item for item in data.assumptions if not item.startswith("Assumed book") and not item.startswith("No real portfolio file")],
        ],
        data_sources=[*data.data_sources, f"portfolio:{path}"],
    )
