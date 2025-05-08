# modules/ggTipsModule/ggTipsTabs/paymentMethodsTab.py

import streamlit as st
import pandas as pd
import altair as alt

def show(data: dict | None = None) -> None:
    st.subheader("Payment Methods Over Time")

    tips = data.get("ggtips", pd.DataFrame()).copy()
    if tips.empty or "payment processor" not in tips.columns:
        st.info("No info about payment procoessor.")
        return

    # Приводим дату в datetime
    tips["date"] = pd.to_datetime(tips["date"], errors="coerce")
    tips = tips.dropna(subset=["date", "payment processor"])

    # Группируем по неделям и месяцам
    tips = tips.assign(
        Week  = lambda df: df["date"].dt.to_period("W").dt.start_time,
        Month = lambda df: df["date"].dt.to_period("M").dt.start_time
    )

    # Подсчёт транзакций по способам оплаты
    weekly = (
        tips.groupby(["Week", "payment processor"], observed=True)
            .size()
            .reset_index(name="Count")
    )
    monthly = (
        tips.groupby(["Month", "payment processor"], observed=True)
            .size()
            .reset_index(name="Count")
    )
    overall = (
        tips["payment processor"]
            .value_counts()
            .reset_index()
            .rename(columns={"index":"payment processor", "payment processor":"Count"})
    )

    # Вкладки
    tab_w, tab_m, tab_o = st.tabs(["Weekly", "Monthly", "Overall"])

    with tab_w:
        st.markdown("#### Weekly ")
        chart_w = (
            alt.Chart(weekly)
            .mark_line(point=True, strokeWidth=2)
            .encode(
                x=alt.X("Week:T", title="Week"),
                y=alt.Y("Count:Q", title="Transactions"),
                color=alt.Color("payment processor:N", title="Processor"),
                tooltip=["Week:T","payment processor:N","Count:Q"]
            )
            .properties(height=300)
            .configure_axis(labelColor="white", titleColor="white")
        )
        st.altair_chart(chart_w, use_container_width=True)

    with tab_m:
        st.markdown("#### MOnthly")
        chart_m = (
            alt.Chart(monthly)
            .mark_line(point=True, strokeWidth=2)
            .encode(
                x=alt.X("Month:T", title="Month"),
                y=alt.Y("Count:Q", title="Transactions"),
                color=alt.Color("payment processor:N", title="Processor"),
                tooltip=["Month:T","payment processor:N","Count:Q"]
            )
            .properties(height=300)
            .configure_axis(labelColor="white", titleColor="white")
        )
        st.altair_chart(chart_m, use_container_width=True)

    with tab_o:
        st.markdown("#### All time")
        chart_o = (
            alt.Chart(overall)
            .mark_line(point=True, strokeWidth=2)
            .encode(
                x=alt.X("payment processor:N", title="Processor"),
                y=alt.Y("Count:Q", title="Transactions"),
                color=alt.Color("payment processor:N", legend=None),
                tooltip=["payment processor:N","Count:Q"]
            )
            .properties(height=200)
            .configure_axis(labelColor="white", titleColor="white")
        )
        st.altair_chart(chart_o, use_container_width=True)
