#!/usr/bin/env python3
"""Compress raw click_stream.csv into one row per session.

The raw Kaggle clickstream is large. This script reads it in chunks, aggregates
session-level funnel/behavior flags, then combines partial session summaries in
case a session crosses a chunk boundary.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

EVENTS = [
    "HOMEPAGE",
    "SEARCH",
    "ITEM_DETAIL",
    "ADD_TO_CART",
    "PROMO_PAGE",
    "ADD_PROMO",
    "BOOKING",
]


def summarize_chunk(df: pd.DataFrame) -> pd.DataFrame:
    base = (
        df.groupby("session_id", sort=False)
        .agg(
            first_event_time=("event_time", "min"),
            last_event_time=("event_time", "max"),
            traffic_source=("traffic_source", "first"),
            event_count=("event_name", "size"),
        )
    )

    counts = pd.crosstab(df["session_id"], df["event_name"])
    for event in EVENTS:
        if event not in counts.columns:
            counts[event] = 0
    counts = counts[EVENTS]
    counts.columns = [f"{x.lower()}_count" for x in counts.columns]
    return base.join(counts, how="left").reset_index()


def combine(parts: list[pd.DataFrame]) -> pd.DataFrame:
    df = pd.concat(parts, ignore_index=True)
    count_cols = [f"{x.lower()}_count" for x in EVENTS]
    agg = {
        "first_event_time": "min",
        "last_event_time": "max",
        "traffic_source": "first",
        "event_count": "sum",
        **{c: "sum" for c in count_cols},
    }
    out = df.groupby("session_id", as_index=False, sort=False).agg(agg)

    out["homepage_count"] = out.pop("homepage_count")
    out["search_count"] = out.pop("search_count")
    out["item_detail_count"] = out.pop("item_detail_count")
    out["add_to_cart_count"] = out.pop("add_to_cart_count")
    out["promo_page_count"] = out.pop("promo_page_count")
    out["add_promo_count"] = out.pop("add_promo_count")
    out["booking_count"] = out.pop("booking_count")

    out["did_search"] = (out["search_count"] > 0).astype("int8")
    out["viewed_item"] = (out["item_detail_count"] > 0).astype("int8")
    out["added_to_cart"] = (out["add_to_cart_count"] > 0).astype("int8")
    out["visited_promo"] = (out["promo_page_count"] > 0).astype("int8")
    out["added_promo"] = (out["add_promo_count"] > 0).astype("int8")
    out["booked"] = (out["booking_count"] > 0).astype("int8")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--chunksize", type=int, default=500_000)
    args = p.parse_args()

    parts: list[pd.DataFrame] = []
    usecols = ["session_id", "event_name", "event_time", "traffic_source"]

    for i, chunk in enumerate(
        pd.read_csv(args.input, usecols=usecols, chunksize=args.chunksize), start=1
    ):
        print(f"Processing chunk {i:,} ...")
        parts.append(summarize_chunk(chunk))

    print("Combining session summaries ...")
    final = combine(parts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(args.output, index=False)
    print(f"Wrote {len(final):,} sessions → {args.output}")


if __name__ == "__main__":
    main()
