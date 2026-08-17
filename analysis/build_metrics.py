#!/usr/bin/env python3
"""Rebuild aggregated metrics used by the StylePulse dashboard.

Expected source files in --data-dir:
  customer.csv
  product.csv
  transactions.csv OR transactions_part_*.csv
  clickstream_sessions.csv OR clickstream_sessions_part_*.csv

The script intentionally publishes aggregate outputs only.
"""
from __future__ import annotations

import argparse
import gc
import glob
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd


def pick_files(data_dir: Path, exact: str, pattern: str) -> list[str]:
    p = data_dir / exact
    if p.exists():
        return [str(p)]
    files = sorted(glob.glob(str(data_dir / pattern)))
    if not files:
        raise FileNotFoundError(f"Missing {exact} (or {pattern}) in {data_dir}")
    return files


def cv(v):
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return None if np.isnan(v) else float(v)
    if pd.isna(v):
        return None
    return v


def records(df: pd.DataFrame):
    return [{k: cv(v) for k, v in row.items()} for row in df.to_dict("records")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument(
        "--site-data",
        type=Path,
        default=None,
        help="Optional path to write dashboard_data.js for the static site",
    )
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    customer_file = args.data_dir / "customer.csv"
    product_file = args.data_dir / "product.csv"
    tx_files = pick_files(args.data_dir, "transactions.csv", "transactions_part_*.csv")
    click_files = pick_files(
        args.data_dir, "clickstream_sessions.csv", "clickstream_sessions_part_*.csv"
    )

    cust = pd.read_csv(
        customer_file,
        usecols=["customer_id", "first_join_date", "device_type", "gender"],
    )
    cust["first_join_date"] = pd.to_datetime(cust.first_join_date, errors="coerce")

    prod = pd.read_csv(
        product_file,
        usecols=["id", "masterCategory", "subCategory"],
        on_bad_lines="skip",
    )

    click_cols = [
        "session_id",
        "traffic_source",
        "event_count",
        "homepage_count",
        "did_search",
        "viewed_item",
        "added_to_cart",
        "visited_promo",
        "added_promo",
        "booked",
    ]
    click = pd.concat(
        [pd.read_csv(f, usecols=click_cols) for f in click_files], ignore_index=True
    )

    tx_cols = [
        "created_at",
        "customer_id",
        "booking_id",
        "session_id",
        "payment_method",
        "payment_status",
        "promo_amount",
        "promo_code",
        "total_amount",
    ]
    tx = pd.concat([pd.read_csv(f, usecols=tx_cols) for f in tx_files], ignore_index=True)
    tx["created_at"] = pd.to_datetime(tx.created_at, utc=True, errors="coerce")
    tx["promo_amount"] = pd.to_numeric(tx.promo_amount, errors="coerce").fillna(0)
    tx["total_amount"] = pd.to_numeric(tx.total_amount, errors="coerce")
    tx["used_promo"] = tx.promo_amount.gt(0)

    quality = {
        "customer_rows": len(cust),
        "customer_unique_ids": cust.customer_id.nunique(),
        "product_parsed_rows": len(prod),
        "clickstream_session_rows": len(click),
        "clickstream_unique_sessions": click.session_id.nunique(),
        "transaction_rows": len(tx),
        "transaction_unique_sessions": tx.session_id.nunique(),
        "transaction_unique_bookings": tx.booking_id.nunique(),
        "transaction_sessions_missing_clickstream": (~tx.session_id.isin(click.session_id)).sum(),
        "transaction_customer_ids_missing_customer_table": (~tx.customer_id.isin(cust.customer_id)).sum(),
    }

    success = (
        tx.loc[
            tx.payment_status.eq("Success"),
            [
                "created_at",
                "customer_id",
                "booking_id",
                "session_id",
                "payment_method",
                "promo_amount",
                "promo_code",
                "total_amount",
                "used_promo",
            ],
        ]
        .copy()
        .sort_values(["customer_id", "created_at", "booking_id"])
        .reset_index(drop=True)
    )
    success["purchase_number"] = success.groupby("customer_id").cumcount() + 1
    success["is_repeat_purchase"] = success.purchase_number.gt(1)
    data_end = success.created_at.max()
    orders_per_customer = success.groupby("customer_id").size()

    core = {
        "registered_customers": cust.customer_id.nunique(),
        "journey_sessions": click.session_id.nunique(),
        "transacting_customers": tx.customer_id.nunique(),
        "successful_buyers": success.customer_id.nunique(),
        "transactions": len(tx),
        "successful_transactions": len(success),
        "payment_success_rate": len(success) / len(tx),
        "registered_to_successful_buyer_rate": success.customer_id.nunique()
        / cust.customer_id.nunique(),
        "repeat_buyers": (orders_per_customer >= 2).sum(),
        "repeat_buyer_rate": (orders_per_customer >= 2).mean(),
        "avg_orders_per_buyer": orders_per_customer.mean(),
        "median_orders_per_buyer": orders_per_customer.median(),
        "gmv_source_units": success.total_amount.sum(),
        "aov_source_units": success.total_amount.mean(),
        "median_order_value_source_units": success.total_amount.median(),
        "promo_order_share": success.used_promo.mean(),
        "promo_gmv_share": success.loc[success.used_promo, "total_amount"].sum()
        / success.total_amount.sum(),
        "data_start": str(success.created_at.min()),
        "data_end": str(data_end),
    }

    # Payment performance.
    payment = tx.groupby("payment_method").payment_status.value_counts().unstack(fill_value=0)
    payment["transactions"] = payment.sum(axis=1)
    payment["successes"] = payment.get("Success", 0)
    payment["success_rate"] = payment.successes / payment.transactions
    payment["failure_rate"] = 1 - payment.success_rate
    payment = (
        payment.reset_index()[
            ["payment_method", "transactions", "successes", "success_rate", "failure_rate"]
        ]
        .sort_values("transactions", ascending=False)
    )

    # Session-level funnel and source quality.
    tx_status = tx.set_index("session_id")["payment_status"]
    tx_amount = tx.set_index("session_id")["total_amount"]
    click["payment_status"] = click.session_id.map(tx_status)
    click["total_amount"] = click.session_id.map(tx_amount)
    click["purchase_success"] = click.payment_status.eq("Success")

    funnel = [
        {"stage": "Homepage / journey", "sessions": int((click.homepage_count > 0).sum())},
        {"stage": "Add to cart", "sessions": int(click.added_to_cart.sum())},
        {"stage": "Booking", "sessions": int(click.booked.sum())},
        {"stage": "Successful payment", "sessions": int(click.purchase_success.sum())},
    ]
    base = funnel[0]["sessions"]
    for row in funnel:
        row["rate"] = row["sessions"] / base

    behavior = [
        {"event": "Search", "sessions": int(click.did_search.sum()), "rate": click.did_search.mean()},
        {"event": "Item detail", "sessions": int(click.viewed_item.sum()), "rate": click.viewed_item.mean()},
        {"event": "Promo page", "sessions": int(click.visited_promo.sum()), "rate": click.visited_promo.mean()},
        {"event": "Promo applied", "sessions": int(click.added_promo.sum()), "rate": click.added_promo.mean()},
    ]

    traffic = (
        click.groupby("traffic_source")
        .agg(
            sessions=("session_id", "size"),
            item_detail_rate=("viewed_item", "mean"),
            cart_rate=("added_to_cart", "mean"),
            booking_rate=("booked", "mean"),
            payment_success_rate=("purchase_success", "mean"),
            avg_events=("event_count", "mean"),
            promo_visit_rate=("visited_promo", "mean"),
        )
        .reset_index()
    )
    aov_by_source = click[click.purchase_success].groupby("traffic_source").total_amount.mean()
    traffic["aov_source_units"] = traffic.traffic_source.map(aov_by_source)
    mobile_share = click.traffic_source.eq("MOBILE").mean()

    del tx_status, tx_amount, click
    gc.collect()

    # First purchase and repeat-purchase retention.
    first_idx = success.groupby("customer_id").created_at.idxmin()
    first = success.loc[
        first_idx,
        [
            "customer_id",
            "created_at",
            "used_promo",
            "promo_code",
            "promo_amount",
            "total_amount",
            "session_id",
            "payment_method",
        ],
    ].copy()
    first = first.rename(
        columns={
            "created_at": "first_purchase_at",
            "used_promo": "first_purchase_promo",
            "promo_code": "first_promo_code",
            "total_amount": "first_order_value",
        }
    )
    second = success[success.purchase_number.eq(2)][
        ["customer_id", "created_at", "total_amount"]
    ].rename(
        columns={"created_at": "second_purchase_at", "total_amount": "second_order_value"}
    )
    cp = first.merge(second, on="customer_id", how="left", validate="one_to_one")
    cp["days_to_second"] = (
        cp.second_purchase_at - cp.first_purchase_at
    ).dt.total_seconds() / 86400

    retention_curve = []
    for days in [7, 30, 60, 90]:
        t = cp[cp.first_purchase_at.le(data_end - pd.Timedelta(days=days))].copy()
        t["retained"] = t.second_purchase_at.notna() & t.days_to_second.le(days)
        for is_promo, label in [(False, "No promo"), (True, "Promo")]:
            s = t[t.first_purchase_promo.eq(is_promo)]
            retention_curve.append(
                {
                    "window_days": days,
                    "segment": label,
                    "buyers": len(s),
                    "retained": s.retained.sum(),
                    "rate": s.retained.mean(),
                }
            )

    # D30 raw and acquisition-month-standardized comparison.
    cp30 = cp[cp.first_purchase_at.le(data_end - pd.Timedelta(days=30))].copy()
    cp30["retained_30"] = cp30.second_purchase_at.notna() & cp30.days_to_second.le(30)
    cp30["cohort_month"] = (
        cp30.first_purchase_at.dt.tz_convert(None).dt.to_period("M").astype(str)
    )
    raw_rates = cp30.groupby("first_purchase_promo").retained_30.mean()
    raw_counts = cp30.groupby("first_purchase_promo").size()
    raw_gap = raw_rates.loc[False] - raw_rates.loc[True]

    by_month = (
        cp30.groupby(["cohort_month", "first_purchase_promo"])
        .retained_30.agg(["mean", "count"])
        .reset_index()
    )
    rate_pivot = by_month.pivot(index="cohort_month", columns="first_purchase_promo", values="mean")
    n_pivot = by_month.pivot(index="cohort_month", columns="first_purchase_promo", values="count")
    valid = [
        m
        for m in rate_pivot.dropna().index
        if n_pivot.loc[m, True] >= 50 and n_pivot.loc[m, False] >= 50
    ]
    weights = n_pivot.loc[valid, True]
    adjusted_no = float(np.average(rate_pivot.loc[valid, False], weights=weights))
    adjusted_yes = float(np.average(rate_pivot.loc[valid, True], weights=weights))
    adjusted_gap = adjusted_no - adjusted_yes

    promo_repeat = cp30[cp30.first_purchase_promo & cp30.retained_30]
    second_aov = float(promo_repeat.second_order_value.mean())
    scenario_lift = 0.18
    promo_n = int(raw_counts.loc[True])
    promo_rate = float(raw_rates.loc[True])
    incremental = promo_n * promo_rate * scenario_lift

    promo_comparison = {
        "raw_no_promo_rate": raw_rates.loc[False],
        "raw_promo_rate": raw_rates.loc[True],
        "raw_gap_pp": raw_gap * 100,
        "raw_relative_gap": raw_gap / raw_rates.loc[False],
        "adjusted_no_promo_rate": adjusted_no,
        "adjusted_promo_rate": adjusted_yes,
        "adjusted_gap_pp": adjusted_gap * 100,
        "mature_promo_buyers": promo_n,
        "promo_second_order_aov_source_units": second_aov,
        "scenario_relative_lift": scenario_lift,
        "scenario_incremental_repeat_buyers": incremental,
        "scenario_incremental_gmv_source_units": incremental * second_aov,
    }

    promo_codes = (
        cp30[cp30.first_purchase_promo & cp30.first_promo_code.notna()]
        .groupby("first_promo_code")
        .agg(
            buyers=("customer_id", "size"),
            retention30=("retained_30", "mean"),
            first_aov=("first_order_value", "mean"),
        )
        .reset_index()
        .sort_values("buyers", ascending=False)
    )

    # Monthly trends.
    cust["join_month"] = cust.first_join_date.dt.to_period("M").astype(str)
    signups = cust.groupby("join_month").customer_id.nunique()
    first["first_month"] = first.first_purchase_at.dt.tz_convert(None).dt.to_period("M").astype(str)
    first_buyers = first.groupby("first_month").customer_id.nunique()
    success["month"] = success.created_at.dt.tz_convert(None).dt.to_period("M").astype(str)
    monthly_orders = success.groupby("month").size()
    monthly_buyers = success.groupby("month").customer_id.nunique()
    monthly_value = success.groupby("month").total_amount.sum()
    monthly_promo = success.groupby("month").used_promo.mean()
    monthly_repeat = success.groupby("month").is_repeat_purchase.mean()
    new_value = success[~success.is_repeat_purchase].groupby("month").total_amount.sum()
    returning_value = success[success.is_repeat_purchase].groupby("month").total_amount.sum()

    months = sorted(set(signups.index) | set(first_buyers.index) | set(monthly_orders.index))
    monthly = []
    for month in months:
        total = float(monthly_value.get(month, 0))
        rv = float(returning_value.get(month, 0))
        monthly.append(
            {
                "month": month,
                "signups": int(signups.get(month, 0)),
                "first_buyers": int(first_buyers.get(month, 0)),
                "orders": int(monthly_orders.get(month, 0)),
                "buyers": int(monthly_buyers.get(month, 0)),
                "gmv_source_units": total,
                "promo_order_share": float(monthly_promo.get(month, 0)) if month in monthly_promo.index else 0,
                "repeat_order_share": float(monthly_repeat.get(month, 0)) if month in monthly_repeat.index else 0,
                "new_buyer_gmv": float(new_value.get(month, 0)),
                "returning_buyer_gmv": rv,
                "returning_gmv_share": rv / total if total else 0,
            }
        )

    # Monthly activity-retention heatmap for 2021 cohorts.
    first_month_map = first.set_index("customer_id").first_purchase_at.dt.tz_convert(None).dt.to_period("M")
    sc = success[["customer_id", "created_at"]].copy()
    sc["activity_month"] = sc.created_at.dt.tz_convert(None).dt.to_period("M")
    sc["cohort_month"] = sc.customer_id.map(first_month_map)
    sc["month_index"] = (
        (sc.activity_month.dt.year - sc.cohort_month.dt.year) * 12
        + (sc.activity_month.dt.month - sc.cohort_month.dt.month)
    )
    unique_activity = sc.drop_duplicates(["customer_id", "activity_month"])
    cohort_counts = unique_activity.groupby(["cohort_month", "month_index"]).customer_id.nunique()
    cohort_sizes = (
        first.assign(cohort_month=first.first_purchase_at.dt.tz_convert(None).dt.to_period("M"))
        .groupby("cohort_month")
        .customer_id.nunique()
    )
    heatmap = []
    for cohort in pd.period_range("2021-01", "2021-12", freq="M"):
        row = {"cohort": str(cohort), "size": int(cohort_sizes.get(cohort, 0))}
        for i in range(7):
            row[f"m{i}"] = (
                float(cohort_counts.get((cohort, i), 0) / row["size"]) if row["size"] else None
            )
        heatmap.append(row)

    # Activation lag and device mix.
    profile = first[["customer_id", "first_purchase_at"]].merge(
        cust[["customer_id", "first_join_date"]], on="customer_id", how="left"
    )
    profile["days"] = (
        profile.first_purchase_at.dt.tz_localize(None) - profile.first_join_date
    ).dt.total_seconds() / 86400
    valid_lag = profile.days.ge(0)
    activation_lag = {
        "valid_buyers": valid_lag.sum(),
        "negative_lag_anomalies": ((~valid_lag) & profile.days.notna()).sum(),
        "median_days": profile.loc[valid_lag, "days"].median(),
        "p75_days": profile.loc[valid_lag, "days"].quantile(0.75),
        "p90_days": profile.loc[valid_lag, "days"].quantile(0.90),
    }
    device = cust.groupby("device_type").customer_id.nunique().reset_index(name="customers")
    device["share"] = device.customers / device.customers.sum()

    # Free large transaction-level frames before re-reading basket metadata.
    del tx, success, sc, unique_activity, cp, cp30
    gc.collect()

    # Category merchandise value from successful transaction baskets.
    product_map = prod[["id", "masterCategory", "subCategory"]]
    pattern = r"'product_id':\s*(\d+),\s*'quantity':\s*(\d+),\s*'item_price':\s*(\d+)"
    master_parts, sub_parts = [], []
    total_items = matched_items = 0
    for file in tx_files:
        chunk = pd.read_csv(file, usecols=["payment_status", "product_metadata"])
        chunk = chunk[chunk.payment_status.eq("Success")]
        x = chunk.product_metadata.str.extractall(pattern)
        x.columns = ["product_id", "quantity", "item_price"]
        x = x.astype("int64").reset_index(drop=True)
        total_items += len(x)
        x = x.merge(product_map, left_on="product_id", right_on="id", how="left")
        matched_items += int(x.masterCategory.notna().sum())
        x["merchandise_value"] = x.quantity * x.item_price
        master_parts.append(
            x.groupby("masterCategory", dropna=False)
            .agg(units=("quantity", "sum"), merchandise_value=("merchandise_value", "sum"), line_items=("product_id", "size"))
            .reset_index()
        )
        sub_parts.append(
            x.groupby("subCategory", dropna=False)
            .agg(units=("quantity", "sum"), merchandise_value=("merchandise_value", "sum"), line_items=("product_id", "size"))
            .reset_index()
        )

    category = (
        pd.concat(master_parts)
        .groupby("masterCategory", dropna=False)[["units", "merchandise_value", "line_items"]]
        .sum()
        .reset_index()
        .rename(columns={"masterCategory": "category"})
        .sort_values("merchandise_value", ascending=False)
    )
    category["share"] = category.merchandise_value / category.merchandise_value.sum()
    subcategory = (
        pd.concat(sub_parts)
        .groupby("subCategory", dropna=False)[["units", "merchandise_value", "line_items"]]
        .sum()
        .reset_index()
        .rename(columns={"subCategory": "category"})
        .sort_values("merchandise_value", ascending=False)
    )
    subcategory["share"] = subcategory.merchandise_value / subcategory.merchandise_value.sum()
    quality["successful_line_items_parsed"] = total_items
    quality["successful_line_items_product_matched"] = matched_items
    quality["successful_line_item_product_match_rate"] = matched_items / total_items

    catalog = prod.groupby("masterCategory").size().reset_index(name="products").sort_values("products", ascending=False)
    catalog["share"] = catalog.products / catalog.products.sum()

    insights = [
        {
            "title": "The apparent promo-retention penalty is mostly a cohort-mix effect",
            "type": "retention",
            "detail": f"Naively, first-purchase promo users repeat within 30 days at {raw_rates.loc[True]*100:.1f}% vs {raw_rates.loc[False]*100:.1f}% without promo ({raw_gap*100:.1f} pp gap). After standardizing within acquisition month, the gap falls to {adjusted_gap*100:.1f} pp.",
            "implication": "Do not conclude that discounts cause poor retention from the raw comparison. Target lifecycle experiments by cohort and measure incremental lift.",
        },
        {
            "title": "Retention is the bigger growth lever than checkout recovery",
            "type": "growth",
            "detail": f"Payment success is already {core['payment_success_rate']*100:.1f}%, while only {raw_rates.loc[True]*100:.1f}% of mature promo-acquired buyers make a second purchase within 30 days.",
            "implication": "Prioritize post-purchase habit loops, category reminders, loyalty milestones and personalized recommendations.",
        },
        {
            "title": "Mobile dominates, but source quality is effectively flat",
            "type": "acquisition",
            "detail": f"Mobile contributes {mobile_share*100:.1f}% of journey sessions, while payment success and AOV are nearly identical across Mobile and Web.",
            "implication": "Instrument campaign/referrer-level acquisition before making CAC allocation decisions.",
        },
    ]

    out = {
        "project": {
            "title": "Myntra-Inspired Growth Funnel & Retention Analytics",
            "subtitle": "Independent portfolio case study using a public fashion e-commerce behavioral dataset",
            "dataset": "E-commerce App Transactional Dataset by Aditya Bagus Pratama (Kaggle)",
            "dataset_url": "https://www.kaggle.com/datasets/bytadit/transactional-ecommerce",
            "disclaimer": "Independent portfolio project. Not affiliated with Myntra. Monetary values are shown in source dataset units; no FX conversion is applied.",
        },
        "quality": {k: cv(v) for k, v in quality.items()},
        "core": {k: cv(v) for k, v in core.items()},
        "funnel": funnel,
        "behavior": [{k: cv(v) for k, v in x.items()} for x in behavior],
        "traffic": records(traffic),
        "retention_curve": [{k: cv(v) for k, v in x.items()} for x in retention_curve],
        "promo_comparison": {k: cv(v) for k, v in promo_comparison.items()},
        "promo_codes": records(promo_codes),
        "monthly": monthly,
        "cohort_heatmap": heatmap,
        "activation_lag": {k: cv(v) for k, v in activation_lag.items()},
        "device_mix": records(device),
        "payment_methods": records(payment),
        "catalog_mix": records(catalog),
        "category_sales": records(category),
        "subcategory_sales": records(subcategory.head(15)),
        "insights": insights,
    }

    json_path = args.output_dir / "dashboard_data.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    pd.DataFrame(monthly).to_csv(args.output_dir / "monthly_metrics.csv", index=False)
    pd.DataFrame(retention_curve).to_csv(args.output_dir / "promo_retention_curve.csv", index=False)
    pd.DataFrame(heatmap).to_csv(args.output_dir / "cohort_retention_heatmap.csv", index=False)
    promo_codes.to_csv(args.output_dir / "promo_code_retention.csv", index=False)
    payment.to_csv(args.output_dir / "payment_method_performance.csv", index=False)
    category.to_csv(args.output_dir / "category_sales.csv", index=False)
    subcategory.to_csv(args.output_dir / "subcategory_sales.csv", index=False)

    if args.site_data:
        args.site_data.parent.mkdir(parents=True, exist_ok=True)
        args.site_data.write_text(
            "window.DASHBOARD_DATA = " + json.dumps(out, separators=(",", ":")) + ";\n",
            encoding="utf-8",
        )

    print(f"Wrote aggregated metrics → {args.output_dir}")


if __name__ == "__main__":
    main()
