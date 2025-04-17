# modules/ggTipsModule/ggTipsTabs/CompaniesTipsTab.py
import streamlit as st
import altair as alt
import pandas as pd
import numpy as np


# ────────────────────────────────────────────────────────────────
# helpers
# ────────────────────────────────────────────────────────────────
def _prep_companies_df(tips: pd.DataFrame) -> pd.DataFrame:
    """
    • Фильтрует только завершённые транзакции (Status == finished, если колонка есть)
    • Группирует по Company → Amount (sum) | Count (n)
    • Вычисляет Scope ≈ ½[(Amount / one_avg_tip) + Count]
    • Добавляет «Days since last transaction»
    """
    if tips.empty or "company" not in tips.columns:
        return pd.DataFrame()

    df = tips.copy()

    # ── группировка ─────────────────────────────────────────────
    grouped = (
        df.groupby("company", dropna=False, observed=True)
          .agg(Amount=("amount", "sum"),
               Count=("uuid", "count"))
          .reset_index()
          .rename(columns={"company": "Company"})
    )

    # ── Scope ──────────────────────────────────────────────────
    one_avg_tip = df["amount"].mean() or 1          # защита от нуля
    grouped["Scope"] = ((grouped["Amount"] / one_avg_tip) + grouped["Count"]) / 2
    grouped["Scope"] = grouped["Scope"].round(1)

    # ── Days since last transaction ────────────────────────────
    if "date" in df.columns:
        last_trx = df.groupby("company")["date"].max().reset_index()
        last_trx.columns = ["Company", "Last transaction"]
        grouped = grouped.merge(last_trx, on="Company", how="left")
        today = pd.to_datetime("today").normalize()
        grouped["Days since last transaction"] = (
            today - grouped["Last transaction"].dt.normalize()
        ).dt.days
    else:
        grouped["Last transaction"] = pd.NaT
        grouped["Days since last transaction"] = np.nan

    return grouped.sort_values("Scope", ascending=False, ignore_index=True)


def _alt_chart(df: pd.DataFrame) -> alt.Chart:
    """Bar (Amount) + 2 line‑charts (Count / Scope)"""
    sort_values = (
        df["Company"]
          .dropna()          # NaN убирать обязательно
          .astype(str)
          .tolist()
    )

    x_cat = alt.X(
        "Company:N",
        sort=sort_values,                     # ⇽ фиксируем порядок
        axis=alt.Axis(labelAngle=-90, title="Company"),
    )

    bar = (
        alt.Chart(df)
        .mark_bar(size=30, color="green", stroke="white", strokeWidth=1)
        .encode(
            x=x_cat,
            y=alt.Y("Amount:Q", axis=alt.Axis(title="Sum of Tips")),
            tooltip=["Company", "Amount", "Count", "Scope"],
        )
    )

    line_count = (
        alt.Chart(df)
        .mark_line(color="blue", strokeWidth=2)
        .encode(x=x_cat, y="Count:Q", tooltip=["Company", "Amount", "Count", "Scope"])
    )

    line_scope = (
        alt.Chart(df)
        .mark_line(color="purple", strokeWidth=2, opacity=0.7)
        .encode(x=x_cat, y="Scope:Q", tooltip=["Company", "Amount", "Count", "Scope"])
    )

    return (
        alt.layer(bar, line_count, line_scope)
        .resolve_scale(y="independent")
        .configure_axis(labelColor='white', titleColor='white')
    )


# ────────────────────────────────────────────────────────────────
# main entry
# ────────────────────────────────────────────────────────────────
def show(data: dict | None = None) -> None:
    """Отображает вкладку «Top Companies»."""

    tips_df: pd.DataFrame = (data or {}).get("ggtips", pd.DataFrame())
    if tips_df.empty:
        st.info("No data for Top Companies yet.")
        return

    companies_df = _prep_companies_df(tips_df)
    if companies_df.empty:
        st.info("Nothing to aggregate for companies.")
        return

    # ── UI – настройки ──────────────────────────────────────────
    with st.expander("Config", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            sort_col = st.selectbox(
                "Select column for sorting",
                ["Scope", "Amount", "Count"],
                key="cmp_sort_col",
            )
        with col2:
            sort_dir = st.selectbox(
                "Select sort direction",
                ["Descending", "Ascending"],
                key="cmp_sort_dir",
            )

        top_n = st.number_input(
            "Top N companies", min_value=1, value=15, step=1, key="cmp_top_n"
        )

    # ── сортировка + Top N ──────────────────────────────────────
    companies_df = companies_df.sort_values(
        sort_col, ascending=(sort_dir == "Ascending"), ignore_index=True
    )
    top_df = companies_df.head(top_n).copy()

    # ── график ──────────────────────────────────────────────────
    st.altair_chart(_alt_chart(top_df), use_container_width=True)

    # ── таблица ─────────────────────────────────────────────────
    with st.expander("Table", expanded=False):
        mode = st.radio("Show", ["Top N", "All"], horizontal=True, key="cmp_tbl_mode")
        tbl = top_df if mode == "Top N" else companies_df

        tbl = tbl.reset_index(drop=True)
        tbl.index += 1                                   # красивый счётчик

        st.dataframe(
            tbl[
                [
                    "Company",
                    "Amount",
                    "Count",
                    "Scope",
                    "Days since last transaction",
                ]
            ],
            use_container_width=True,
        )
