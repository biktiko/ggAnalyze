import streamlit as st
import pandas as pd
import altair as alt
import numpy as np

def show(data: dict | None = None) -> None:
    st.subheader("Companies Activity Change")

    orders_df = data.get("orders", pd.DataFrame()).copy()
    clients_df = data.get("clients", pd.DataFrame()).copy()

    if orders_df.empty or clients_df.empty:
        st.info("No data available for analysis.")
        return

    orders_df["date"] = pd.to_datetime(orders_df["date"], errors="coerce")
    clients_df = clients_df[["userid", "company"]].dropna()

    # Объединяем название компании в заказах
    merged = orders_df.merge(clients_df, on="userid", how="left")
    merged = merged.dropna(subset=["company", "date", "orders"])

    with st.expander("Config", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            period_a = st.date_input("Period A", [], key="perA")
        with col2:
            period_b = st.date_input("Period B", [], key="perB")

        format_option = st.selectbox("Display format", ["Numbers", "Percentage"])
        threshold = st.number_input(
            "Max abs diff for plot", min_value=0.0, value=5.0, step=1.0
        )

    if len(period_a) != 2 or len(period_b) != 2:
        st.warning("Please select both periods completely.")
        return

    # Фильтрация по периодам
    df_a = merged[(merged["date"] >= pd.to_datetime(period_a[0])) &
                  (merged["date"] <= pd.to_datetime(period_a[1]))]
    df_b = merged[(merged["date"] >= pd.to_datetime(period_b[0])) &
                  (merged["date"] <= pd.to_datetime(period_b[1]))]

    # Агрегация
    grp_a = df_a.groupby("company", observed=True).agg(Orders_A=("orders", "sum"))
    grp_b = df_b.groupby("company", observed=True).agg(Orders_B=("orders", "sum"))

    df = grp_a.join(grp_b, how="outer").fillna(0).reset_index()

    days_a = (pd.to_datetime(period_a[1]) - pd.to_datetime(period_a[0])).days or 1
    days_b = (pd.to_datetime(period_b[1]) - pd.to_datetime(period_b[0])).days or 1

    df["Scope_A"] = df["Orders_A"] / days_a
    df["Scope_B"] = df["Orders_B"] / days_b

    df["DiffNum"] = df["Scope_B"] - df["Scope_A"]
    df["DiffPercent"] = ((df["DiffNum"] / df["Scope_A"].replace(0, np.nan)) * 100).fillna(-100)

    diff_col = "DiffNum" if format_option == "Numbers" else "DiffPercent"
    df["DiffPlot"] = df[diff_col].clip(lower=-threshold, upper=threshold)

    df = df.sort_values(diff_col, ascending=False, ignore_index=True)

    order = df["company"].tolist()
    chart = alt.Chart(df).mark_bar().encode(
        y=alt.Y("company:N", sort=order),
        x=alt.X("DiffPlot:Q", title="Δ Activity"),
        color=alt.condition(
            alt.datum[diff_col] >= 0, alt.value("green"), alt.value("red")
        ),
        tooltip=[
            "company",
            alt.Tooltip("Scope_A:Q", title="Scope A", format=".2f"),
            alt.Tooltip("Scope_B:Q", title="Scope B", format=".2f"),
            alt.Tooltip(f"{diff_col}:Q", title=diff_col, format=".2f"),
        ]
    )

    st.altair_chart(chart, use_container_width=True)

    with st.expander("Details"):
        st.dataframe(df)
