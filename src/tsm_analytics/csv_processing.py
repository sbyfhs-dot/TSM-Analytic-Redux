from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import pandas as pd


@dataclass
class ColumnMapping:
    timestamp: str
    price: str
    item: Optional[str] = None
    quantity: Optional[str] = None


TIMESTAMP_HINTS = ("time", "timestamp", "soldat", "sold_at", "date")
PRICE_HINTS = ("price", "gold", "copper", "amount", "value")
ITEM_HINTS = ("item", "itemstring", "item_name", "name")
QUANTITY_HINTS = ("qty", "quantity", "count", "stack")


def _find_column(headers: Iterable[str], hints: Iterable[str]) -> Optional[str]:
    lowered = {h.lower(): h for h in headers}
    for key, original in lowered.items():
        if any(hint in key for hint in hints):
            return original
    return None


def autodetect_mapping(headers: list[str]) -> ColumnMapping:
    return ColumnMapping(
        timestamp=_find_column(headers, TIMESTAMP_HINTS) or "",
        price=_find_column(headers, PRICE_HINTS) or "",
        item=_find_column(headers, ITEM_HINTS),
        quantity=_find_column(headers, QUANTITY_HINTS),
    )


def has_required_mapping(mapping: ColumnMapping) -> bool:
    return bool(mapping.timestamp and mapping.price)


def extract_headers(csv_path: str) -> list[str]:
    return list(pd.read_csv(csv_path, nrows=0).columns)


def normalize_sales_data(csv_path: str, mapping: ColumnMapping) -> pd.DataFrame:
    usecols = [mapping.timestamp, mapping.price]
    if mapping.item:
        usecols.append(mapping.item)
    if mapping.quantity:
        usecols.append(mapping.quantity)

    frame = pd.read_csv(csv_path, usecols=usecols, low_memory=False)

    normalized = pd.DataFrame()
    normalized["raw_timestamp"] = pd.to_numeric(frame[mapping.timestamp], errors="coerce")
    normalized = normalized.dropna(subset=["raw_timestamp"])

    # TSM exports are generally unix seconds. Some exports may be ms precision.
    ts = normalized["raw_timestamp"]
    divisor = 1000 if ts.median() > 10_000_000_000 else 1
    normalized["timestamp"] = pd.to_datetime(ts / divisor, unit="s", errors="coerce")
    normalized = normalized.dropna(subset=["timestamp"])

    normalized["price_copper"] = pd.to_numeric(frame.loc[normalized.index, mapping.price], errors="coerce")
    normalized = normalized.dropna(subset=["price_copper"])

    normalized["price_gold"] = normalized["price_copper"] / 10_000

    if mapping.quantity:
        normalized["quantity"] = pd.to_numeric(frame.loc[normalized.index, mapping.quantity], errors="coerce").fillna(1)
    else:
        normalized["quantity"] = 1

    normalized["quantity"] = normalized["quantity"].clip(lower=1).astype(int)

    if mapping.item:
        normalized["item"] = frame.loc[normalized.index, mapping.item].astype(str).fillna("Unknown")
    else:
        normalized["item"] = "(All Items)"

    normalized["local_time"] = normalized["timestamp"].dt.tz_localize("UTC").dt.tz_convert(None)
    normalized["date"] = normalized["local_time"].dt.date

    return normalized[["local_time", "date", "price_copper", "price_gold", "quantity", "item"]].sort_values("local_time")


def daily_aggregates(filtered: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    daily_gold = filtered.groupby("date", as_index=False)["price_gold"].sum()
    daily_sales = filtered.groupby("date", as_index=False).size().rename(columns={"size": "sales_count"})
    return {
        "gold_per_day": daily_gold,
        "sales_per_day": daily_sales,
    }
