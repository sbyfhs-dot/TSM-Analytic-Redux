from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
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
ITEM_ID_PATTERN = re.compile(r"i:(\d+)")


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


def load_item_name_map(mapping_path: Optional[str] = None) -> Dict[str, str]:
    path = Path(mapping_path) if mapping_path else Path(__file__).resolve().parents[2] / "data" / "item_names.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_item_id(item_value: object) -> Optional[int]:
    if item_value is None:
        return None
    match = ITEM_ID_PATTERN.search(str(item_value))
    if not match:
        return None
    return int(match.group(1))


def format_copper(copper_value: int) -> str:
    copper = int(copper_value)
    gold = copper // 10_000
    silver = (copper % 10_000) // 100
    copper_only = copper % 100
    parts = []
    if gold > 0:
        parts.append(f"{gold}g")
    if silver > 0 or gold > 0:
        parts.append(f"{silver}s")
    parts.append(f"{copper_only}c")
    return " ".join(parts)


def normalize_sales_data(csv_path: str, mapping: ColumnMapping, item_name_map: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    usecols = [mapping.timestamp, mapping.price]
    if mapping.item:
        usecols.append(mapping.item)
    if mapping.quantity:
        usecols.append(mapping.quantity)

    frame = pd.read_csv(csv_path, usecols=usecols, low_memory=False)

    normalized = pd.DataFrame()
    normalized["raw_timestamp"] = pd.to_numeric(frame[mapping.timestamp], errors="coerce")
    normalized = normalized.dropna(subset=["raw_timestamp"])

    ts = normalized["raw_timestamp"]
    divisor = 1000 if ts.median() > 10_000_000_000 else 1
    normalized["timestamp"] = pd.to_datetime(ts / divisor, unit="s", errors="coerce")
    normalized = normalized.dropna(subset=["timestamp"])

    normalized["price_copper"] = pd.to_numeric(frame.loc[normalized.index, mapping.price], errors="coerce")
    normalized = normalized.dropna(subset=["price_copper"])
    normalized["price_copper"] = normalized["price_copper"].round().astype(int).clip(lower=0)

    if mapping.quantity:
        normalized["quantity"] = pd.to_numeric(frame.loc[normalized.index, mapping.quantity], errors="coerce").fillna(1)
    else:
        normalized["quantity"] = 1
    normalized["quantity"] = normalized["quantity"].clip(lower=1).astype(int)

    if mapping.item:
        normalized["item"] = frame.loc[normalized.index, mapping.item].astype(str).fillna("Unknown")
    else:
        normalized["item"] = "(All Items)"

    normalized["item_id"] = normalized["item"].apply(parse_item_id)
    name_map = item_name_map if item_name_map is not None else load_item_name_map()

    def resolve_name(row: pd.Series) -> str:
        item_id = row["item_id"]
        item_raw = row["item"]
        if item_id is None:
            return f"Unknown ({item_raw})"
        return name_map.get(str(item_id), f"Unknown (i:{item_id})")

    normalized["item_name"] = normalized[["item", "item_id"]].apply(resolve_name, axis=1)

    normalized["price_gold"] = normalized["price_copper"] / 10_000
    normalized["price_display"] = normalized["price_copper"].apply(format_copper)

    normalized["total_copper"] = normalized["price_copper"] * normalized["quantity"]
    normalized["total_gold"] = normalized["total_copper"] / 10_000
    normalized["total_display"] = normalized["total_copper"].apply(format_copper)

    normalized["local_time"] = normalized["timestamp"].dt.tz_localize("UTC").dt.tz_convert(None)
    normalized["date"] = normalized["local_time"].dt.date

    columns = [
        "local_time",
        "date",
        "item",
        "item_id",
        "item_name",
        "quantity",
        "price_copper",
        "price_gold",
        "price_display",
        "total_copper",
        "total_gold",
        "total_display",
    ]
    return normalized[columns].sort_values("local_time")


def aggregate_sales(frame: pd.DataFrame, freq: str = "D", by_item: bool = False) -> Dict[str, pd.DataFrame]:
    if frame.empty:
        return {"gold": pd.DataFrame(), "sales": pd.DataFrame()}

    keyed = frame.copy()
    keyed = keyed.set_index("local_time")

    if by_item:
        gold = (
            keyed.groupby("item_name")
            .resample(freq)["total_gold"]
            .sum()
            .reset_index()
            .rename(columns={"total_gold": "gold"})
        )
    else:
        gold = keyed.resample(freq)["total_gold"].sum().reset_index().rename(columns={"total_gold": "gold"})

    sales = keyed.resample(freq).size().reset_index().rename(columns={0: "sales_count"})
    return {"gold": gold, "sales": sales}
