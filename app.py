"""
Settlement Coverage Analysis
-----------------------------
A Streamlit port of the KNIME workflow 'Coverage_Analysis_v2.1'.

Pipeline (mirrors the KNIME nodes):
 1. Load CSV (QGIS settlement-extent export)               -> CSV Reader
 2. Flag each grid point as Visited (1) / Not Visited (0)   -> Rule Engine
 3. Group by LGA / Ward / Settlement, sum & count visits    -> GroupBy
 4. Compute % of Visitation per settlement                  -> Math Formula
 5. Classify into coverage buckets                          -> Rule Engine
 6. Pivot: count of settlements per LGA x Coverage bucket    -> Pivot
 7. Filter out Not Visited / Low Coverage settlements        -> Rule-based Row Filter
 8. Let the user download each result as .xlsx               -> Excel Writer
"""

import io
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Settlement Coverage Analysis", layout="wide")

COVERAGE_ORDER = ["Not Visited", "Low Coverage", "Partially Covered", "Fully Covered"]
COVERAGE_COLORS = {
    "Not Visited": "#d62728",
    "Low Coverage": "#ff7f0e",
    "Partially Covered": "#f1c40f",
    "Fully Covered": "#2ca02c",
}


def classify_coverage(pct: float) -> str:
    """Same thresholds as the KNIME 'Coverage Analysis' Rule Engine node."""
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


def guess_column(columns, candidates):
    for c in candidates:
        if c in columns:
            return c
    return columns[0]


# ---------------------------------------------------------------- Header ---
st.title("📍 Settlement Coverage Analysis")
st.caption(
    "Python / Streamlit rebuild of the KNIME workflow **Coverage_Analysis_v2.1**"
)

with st.expander("ℹ️ What this app does / how it maps to the KNIME workflow"):
    st.markdown(
        """
This app filters settlement visitation records and calculates the number of
**Visited** vs **Not Visited** points per settlement. It then works out the
**% of Visitation** for each settlement and classifies it as:

- **Not Visited** — 0% visited
- **Low Coverage** — 1–49% visited
- **Partially Covered** — 50–79% visited
- **Fully Covered** — ≥ 80% visited

It then summarizes coverage by **LGA** (a pivot table) and produces a
follow-up list of settlements that are **Not Visited** or **Low Coverage**.

**Note on the original KNIME file:** the KNIME pivot branch (`GroupBy` →
`Pivot` → `Missing Value`) referenced column names (`lga`, `settlement`,
`LGA`) that didn't exist in the CSV Reader's output (`lga_name`,
`settlement_name`) — those nodes were never actually executed in the saved
workflow (their KNIME state was `IDLE`/`CONFIGURED`, not `EXECUTED`). This
app fixes that mismatch and uses the real column names, so the LGA pivot
here is a corrected, working version of what the workflow intended.
The "TimeSpent"/"number of mins" nodes in the original workflow were also
mislabeled leftovers (the "number of mins" column was actually a sum of
`NUMPOINTS`, not time) and don't feed into coverage at all, so they're
omitted here.
        """
    )

# ------------------------------------------------------------- File input --
uploaded_file = st.file_uploader(
    "Upload the settlement visitation CSV (QGIS export)", type=["csv"]
)

if uploaded_file is None:
    st.info("👆 Upload a CSV to get started. Expected columns include something "
             "like `lga_name`, `ward_name`, `settlement_name`, `visitation`, "
             "and a points column (e.g. `NUMPOINTS`).")
    st.stop()


@st.cache_data(show_spinner=False)
def load_csv(file) -> pd.DataFrame:
    return pd.read_csv(file)


raw_df = load_csv(uploaded_file)
st.success(f"Loaded {len(raw_df):,} rows and {len(raw_df.columns)} columns.")

with st.expander("Preview raw data"):
    st.dataframe(raw_df.head(50), width="stretch")

# --------------------------------------------------------- Column mapping --
st.sidebar.header("Column mapping")
st.sidebar.caption("Match your CSV's columns to what the analysis needs.")
cols = raw_df.columns.tolist()

lga_col = st.sidebar.selectbox(
    "LGA column", cols, index=cols.index(guess_column(cols, ["lga_name", "grid_lga", "LGA"]))
)
ward_col = st.sidebar.selectbox(
    "Ward column", cols, index=cols.index(guess_column(cols, ["ward_name", "grid_ward", "Ward"]))
)
settlement_col = st.sidebar.selectbox(
    "Settlement column",
    cols,
    index=cols.index(guess_column(cols, ["settlement_name", "grid_settlement", "Settlement"])),
)
visitation_col = st.sidebar.selectbox(
    "Visitation status column",
    cols,
    index=cols.index(guess_column(cols, ["visitation", "visit_status"])),
)
points_col = st.sidebar.selectbox(
    "Points / building count column (summed per settlement)",
    cols,
    index=cols.index(guess_column(cols, ["NUMPOINTS", "building_count"])),
)

visited_label = st.sidebar.text_input("Value meaning 'Visited'", "Visited")
not_visited_label = st.sidebar.text_input("Value meaning 'Not Visited'", "Not Visited")

# --------------------------------------------------- Step 1: Visited flag --
df = raw_df.copy()
status = df[visitation_col].astype(str).str.strip()
df["Visited_flag"] = np.select(
    [status.str.lower() == visited_label.strip().lower(),
     status.str.lower() == not_visited_label.strip().lower()],
    [1, 0],
    default=np.nan,
)

unmatched = int(df["Visited_flag"].isna().sum())
if unmatched:
    st.warning(
        f"{unmatched:,} rows had a visitation value that didn't match "
        f"'{visited_label}' or '{not_visited_label}' and were excluded from counts."
    )

# ------------------------------------------- Step 2: GroupBy per settlement -
settlement_level = (
    df.groupby([lga_col, ward_col, settlement_col], as_index=False)
    .agg(**{
        "Sum(Visited_flag)": ("Visited_flag", "sum"),
        "Count(Visited_flag)": ("Visited_flag", "count"),
        "Sum(Points)": (points_col, "sum"),
    })
)

# ------------------------------------------ Step 3: % of Visitation --------
settlement_level["% of Visitation"] = (
    settlement_level["Sum(Visited_flag)"] / settlement_level["Count(Visited_flag)"] * 100
).round(2)

# ------------------------------------------ Step 4: Coverage classification-
settlement_level["Coverage"] = settlement_level["% of Visitation"].apply(classify_coverage)
settlement_level["Coverage"] = pd.Categorical(
    settlement_level["Coverage"], categories=COVERAGE_ORDER, ordered=True
)

# ---------------------------------------------------------- Results: KPIs --
st.header("Results")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Settlements analyzed", f"{len(settlement_level):,}")
k2.metric("Fully Covered", f"{(settlement_level['Coverage'] == 'Fully Covered').sum():,}")
k3.metric("Not Visited", f"{(settlement_level['Coverage'] == 'Not Visited').sum():,}")
k4.metric(
    "Overall % Visitation",
    f"{settlement_level['Sum(Visited_flag)'].sum() / settlement_level['Count(Visited_flag)'].sum() * 100:.1f}%",
)

# ---------------------------------------------------- Tab 1: Settlement lvl-
tab1, tab2, tab3 = st.tabs(
    ["📋 Settlement-level (raw output)", "📊 Coverage by LGA (pivot)", "🚩 Follow-up list"]
)

with tab1:
    st.subheader("Settlement-level Coverage")
    st.dataframe(settlement_level, width="stretch")
    st.download_button(
        "⬇️ Download Settlement-level Excel",
        data=to_excel_bytes(settlement_level, "Settlement_Level"),
        file_name="Settlement_level_RAW.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# --------------------------------------------------- Step 5: Pivot by LGA --
with tab2:
    pivot = (
        settlement_level.groupby([lga_col, "Coverage"], observed=False)[settlement_col]
        .count()
        .unstack(fill_value=0)
        .reindex(columns=COVERAGE_ORDER, fill_value=0)
    )
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.reset_index().rename(columns={lga_col: "LGA"})

    st.subheader("Coverage by LGA")
    st.dataframe(pivot, width="stretch")

    chart_df = pivot.set_index("LGA")[COVERAGE_ORDER]
    st.bar_chart(chart_df, color=[COVERAGE_COLORS[c] for c in COVERAGE_ORDER])

    st.download_button(
        "⬇️ Download LGA-level Excel",
        data=to_excel_bytes(pivot, "LGA_Level_Coverage"),
        file_name="LGA_Level_Coverage.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# ------------------------------------------------- Step 6: Follow-up list --
with tab3:
    followup = settlement_level[
        settlement_level["Coverage"].isin(["Not Visited", "Low Coverage"])
    ].sort_values([lga_col, "% of Visitation"])

    st.subheader("Settlements needing follow-up (Not Visited / Low Coverage)")
    st.dataframe(followup, width="stretch")
    st.download_button(
        "⬇️ Download Follow-up List Excel",
        data=to_excel_bytes(followup, "Missed_LowCovered"),
        file_name="Missed_Low_covered_Settlements.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
