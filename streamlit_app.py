"""Settlement Coverage Analysis — Streamlit Application

Run with: streamlit run streamlit_app.py
"""

import pandas as pd
import streamlit as st

from analysis import (
    COVERAGE_COLORS,
    COVERAGE_ORDER,
    guess_column,
    run_analysis,
    to_excel_bytes,
)

st.set_page_config(page_title="Settlement Coverage Analysis", layout="wide")

st.title("📍 Settlement Coverage Analysis")
st.caption(
    "Python / Streamlit rebuild of the KNIME workflow **Coverage_Analysis_v2.1**"
)

uploaded_file = st.file_uploader(
    "Upload the settlement visitation CSV (QGIS export)", type=["csv"]
)

if uploaded_file is None:
    st.info(
        "👆 Upload a CSV to get started. Expected columns include something "
        "like `lga_name`, `ward_name`, `settlement_name`, `visitation`, "
        "and a points column (e.g. `NUMPOINTS`)."
    )
    st.stop()


@st.cache_data(show_spinner=False)
def load_csv(file) -> pd.DataFrame:
    return pd.read_csv(file)


raw_df = load_csv(uploaded_file)
st.success(f"Loaded {len(raw_df):,} rows and {len(raw_df.columns)} columns.")

with st.expander("Preview raw data"):
    st.dataframe(raw_df.head(50), width="stretch")

st.sidebar.header("Column mapping")
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

results = run_analysis(
    raw_df,
    lga_col=lga_col,
    ward_col=ward_col,
    settlement_col=settlement_col,
    visitation_col=visitation_col,
    points_col=points_col,
    visited_label=visited_label,
    not_visited_label=not_visited_label,
)

for warning in results["warnings"]:
    st.warning(warning)

settlement_level = pd.DataFrame(results["settlement_level"])
pivot = pd.DataFrame(results["pivot"])
followup = pd.DataFrame(results["followup"])

st.header("Results")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Settlements analyzed", f"{results['kpis']['settlements']:,}")
k2.metric("Fully Covered", f"{results['kpis']['fully_covered']:,}")
k3.metric("Not Visited", f"{results['kpis']['not_visited']:,}")
k4.metric("Overall % Visitation", f"{results['kpis']['overall_pct']}%")

tab1, tab2, tab3 = st.tabs(
    ["📋 Settlement-level (raw output)", "📊 Coverage by LGA (pivot)", "🚩 Follow-up list"]
)

with tab1:
    st.dataframe(settlement_level, width="stretch")
    st.download_button(
        "⬇️ Download Settlement-level Excel",
        data=to_excel_bytes(settlement_level, "Settlement_Level"),
        file_name="Settlement_level_RAW.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with tab2:
    st.dataframe(pivot, width="stretch")
    chart_df = pivot.set_index("LGA")[COVERAGE_ORDER]
    st.bar_chart(chart_df, color=[COVERAGE_COLORS[c] for c in COVERAGE_ORDER])
    st.download_button(
        "⬇️ Download LGA-level Excel",
        data=to_excel_bytes(pivot, "LGA_Level_Coverage"),
        file_name="LGA_Level_Coverage.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with tab3:
    st.dataframe(followup, width="stretch")
    st.download_button(
        "⬇️ Download Follow-up List Excel",
        data=to_excel_bytes(followup, "Missed_LowCovered"),
        file_name="Missed_Low_covered_Settlements.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
