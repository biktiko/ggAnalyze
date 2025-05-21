# File: modules/BusinessModule/ggBusinessTabs/activationsTab.py

import streamlit as st
import pandas as pd
import altair as alt
import numpy as np

def show(data: dict | None = None, filters: dict | None = None) -> None:
    """
    Tab 'Companies Activity Change'
    Принимает:
      - data: {"orders": DataFrame, "clients": DataFrame}
      - filters: словарь из get_common_filters()
    """
    st.subheader("Companies Activity Change")

    # расходуем include_weekends
    include_weekends = filters.get("include_weekends", True) if filters else True

    orders_df  = data.get("orders",  pd.DataFrame()).copy()
    clients_df = data.get("clients", pd.DataFrame()).copy()
    if orders_df.empty or clients_df.empty:
        st.info("No data available for analysis.")
        return

    # храним дату как Timestamp
    orders_df["date"] = pd.to_datetime(orders_df["date"], errors="coerce")
    clients_df        = clients_df[["userid","company"]].dropna()

    merged = (
        orders_df
        .merge(clients_df, on="userid", how="left")
        .dropna(subset=["company","date","orders"])
    )
    # исключаем выходные, если нужно
    if not include_weekends:
        merged = merged[merged["date"].dt.weekday < 5]

    # выбор периодов
    with st.expander("Config", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            period_a = st.date_input("Period A", [], key="perA")
        with col2:
            period_b = st.date_input("Period B", [], key="perB")
        format_option = st.selectbox("Display format", ["Numbers","Percentage"])
        threshold     = st.number_input("Max abs diff for plot", min_value=0.0, value=5.0, step=1.0)

    if len(period_a) != 2 or len(period_b) != 2:
        st.warning("Please select both periods completely.")
        return

    # приводим границы к Timestamp
    a0 = pd.to_datetime(period_a[0])
    a1 = pd.to_datetime(period_a[1])
    b0 = pd.to_datetime(period_b[0])
    b1 = pd.to_datetime(period_b[1])

    # фильтруем по периодам
    df_a = merged[(merged["date"] >= a0) & (merged["date"] <= a1)]
    df_b = merged[(merged["date"] >= b0) & (merged["date"] <= b1)]

    # агрегация заказов
    grp_a = df_a.groupby("company", observed=True).agg(Orders_A=("orders","sum"))
    grp_b = df_b.groupby("company", observed=True).agg(Orders_B=("orders","sum"))
    df = grp_a.join(grp_b, how="outer").fillna(0).reset_index()

    # считаем дни для усреднения
    if include_weekends:
        days_a = (a1.date() - a0.date()).days + 1
        days_b = (b1.date() - b0.date()).days + 1
    else:
        days_a = len(pd.bdate_range(a0, a1))
        days_b = len(pd.bdate_range(b0, b1))

    df["Scope_A"] = df["Orders_A"] / days_a
    df["Scope_B"] = df["Orders_B"] / days_b

    df["DiffNum"]     = df["Scope_B"] - df["Scope_A"]
    df["DiffPercent"] = ((df["DiffNum"] / df["Scope_A"].replace(0, np.nan)) * 100).fillna(-100)

    diff_col       = "DiffNum" if format_option=="Numbers" else "DiffPercent"
    df["DiffPlot"] = df[diff_col].clip(lower=-threshold, upper=threshold)
    df = df.sort_values(diff_col, ascending=False, ignore_index=True)

    # отрисовка
    order = df["company"].tolist()
    chart = alt.Chart(df).mark_bar().encode(
        y=alt.Y("company:N", sort=order),
        x=alt.X("DiffPlot:Q", title="Δ Activity"),
        color=alt.condition(
            alt.datum[diff_col]>=0, alt.value("green"), alt.value("red")
        ),
        tooltip=[
            "company",
            alt.Tooltip("Scope_A:Q", title="Scope A", format=".2f"),
            alt.Tooltip("Scope_B:Q", title="Scope B", format=".2f"),
            alt.Tooltip(f"{diff_col}:Q", title=diff_col, format=".2f"),
        ],
    )
    st.altair_chart(chart, use_container_width=True)

    # детали
    with st.expander("Details"):
        st.dataframe(df)
