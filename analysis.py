"""Core settlement coverage analysis (shared by FastAPI and Streamlit)."""

from __future__ import annotations

import io
from typing import Any

import numpy as np
import pandas as pd

COVERAGE_ORDER = ["Not Visited", "Low Coverage", "Partially Covered", "Fully Covered"]
COVERAGE_COLORS = {
    "Not Visited": "#d62728",
    "Low Coverage": "#ff7f0e",
    "Partially Covered": "#f1c40f",
    "Fully Covered": "#2ca02c",
}


def classify_coverage(pct: float) -> str:
    if pd.isna(pct):
        return "Not Visited"
    if pct == 0:
        return "Not Visited"
    if pct <= 49:
        return "Low Coverage"
    if pct <= 79:
        return "Partially Covered"
    return "Fully Covered"


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Sheet1") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


def guess_column(columns: list[str], candidates: list[str]) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return columns[0]


def df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_categorical_dtype(out[col]):
            out[col] = out[col].astype(str)
    return out.where(pd.notna(out), None).to_dict(orient="records")


def run_analysis(
    raw_df: pd.DataFrame,
    lga_col: str,
    ward_col: str,
    settlement_col: str,
    visitation_col: str,
    points_col: str,
    visited_label: str = "Visited",
    not_visited_label: str = "Not Visited",
) -> dict[str, Any]:
    df = raw_df.copy()
    status = df[visitation_col].astype(str).str.strip()
    df["Visited_flag"] = np.select(
        [
            status.str.lower() == visited_label.strip().lower(),
            status.str.lower() == not_visited_label.strip().lower(),
        ],
        [1, 0],
        default=np.nan,
    )

    unmatched = int(df["Visited_flag"].isna().sum())

    settlement_level = (
        df.groupby([lga_col, ward_col, settlement_col], as_index=False)
        .agg(
            **{
                "Sum(Visited_flag)": ("Visited_flag", "sum"),
                "Count(Visited_flag)": ("Visited_flag", "count"),
                "Sum(Points)": (points_col, "sum"),
            }
        )
    )

    settlement_level["% of Visitation"] = (
        settlement_level["Sum(Visited_flag)"]
        / settlement_level["Count(Visited_flag)"]
        * 100
    ).round(2)

    settlement_level["Coverage"] = settlement_level["% of Visitation"].apply(
        classify_coverage
    )
    settlement_level["Coverage"] = pd.Categorical(
        settlement_level["Coverage"], categories=COVERAGE_ORDER, ordered=True
    )

    pivot = (
        settlement_level.groupby([lga_col, "Coverage"], observed=False)[
            settlement_col
        ]
        .count()
        .unstack(fill_value=0)
        .reindex(columns=COVERAGE_ORDER, fill_value=0)
    )
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.reset_index().rename(columns={lga_col: "LGA"})

    followup = settlement_level[
        settlement_level["Coverage"].isin(["Not Visited", "Low Coverage"])
    ].sort_values([lga_col, "% of Visitation"])

    total_visited = settlement_level["Sum(Visited_flag)"].sum()
    total_count = settlement_level["Count(Visited_flag)"].sum()
    overall_pct = round(total_visited / total_count * 100, 1) if total_count else 0.0

    return {
        "kpis": {
            "settlements": len(settlement_level),
            "fully_covered": int(
                (settlement_level["Coverage"] == "Fully Covered").sum()
            ),
            "not_visited": int(
                (settlement_level["Coverage"] == "Not Visited").sum()
            ),
            "overall_pct": overall_pct,
        },
        "warnings": (
            [
                f"{unmatched:,} rows had a visitation value that didn't match "
                f"'{visited_label}' or '{not_visited_label}' and were excluded from counts."
            ]
            if unmatched
            else []
        ),
        "settlement_level": df_to_records(settlement_level),
        "pivot": df_to_records(pivot),
        "followup": df_to_records(followup),
        "chart": {
            "labels": pivot["LGA"].tolist(),
            "datasets": [
                {
                    "label": bucket,
                    "data": pivot[bucket].tolist(),
                    "backgroundColor": COVERAGE_COLORS[bucket],
                }
                for bucket in COVERAGE_ORDER
            ],
        },
        "columns": {
            "lga": lga_col,
            "ward": ward_col,
            "settlement": settlement_col,
        },
    }
