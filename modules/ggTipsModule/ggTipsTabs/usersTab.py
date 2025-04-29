# modules/ggTipsModule/ggTipsTabs/usersTab.py

import io
import streamlit as st
import pandas as pd
import altair as alt

def show(data: dict | None = None) -> None:
    """
    Вкладка «Users» — сводная таблица и тепловая карта,
    показывающие, сколько чаевых (Count или Amount) оставил каждый пользователь в каждой компании,
    а также RFM + Churn-метрики.
    """
    st.subheader("Users Tip Distribution")

    # 1) Исходные данные
    tips = data.get("ggtips", pd.DataFrame()).copy()
    if tips.empty:
        st.info("No tips data to show.")
        return

    # 2) Панель настроек
    with st.expander("Config", expanded=True):
        agg_type = st.selectbox("Value type", ["Count", "Amount"])
        top_n    = st.number_input("Top N users to display", min_value=1, value=15, step=1)
        thresh   = st.slider(
            "Minimum total per user",
            min_value=0.0,
            max_value=float(tips["amount"].max()),
            value=0.0,
            help="Скрыть пользователей с суммой/count ниже этого порога"
        )

    # 3) Pivot-таблица
    pivot = pd.pivot_table(
        tips,
        index="payer",
        columns="company",
        values="amount",
        aggfunc="count" if agg_type == "Count" else "sum",
        fill_value=0,
    )
    pivot["__Total"] = pivot.sum(axis=1)
    pivot = pivot[pivot["__Total"] >= thresh]
    pivot = pivot.sort_values("__Total", ascending=False).head(top_n)
    pivot = pivot.drop(columns="__Total")

    # 4) Отобразить pivot
    st.write(f"Showing top {len(pivot)} users ({agg_type}), threshold ≥ {thresh:.0f}")
    st.dataframe(pivot, use_container_width=True)

    # 5) Тепловая карта
    df_heat = pivot.reset_index().melt(
        id_vars="payer", var_name="Company", value_name="Value"
    )
    heatmap = (
        alt.Chart(df_heat)
        .mark_rect()
        .encode(
            x=alt.X("Company:N", title="Company"),
            y=alt.Y("payer:O", sort=pivot.index.astype(str).tolist(), title="User"),
            color=alt.Color("Value:Q", scale=alt.Scale(scheme="greens"), title=agg_type),
            tooltip=[
                alt.Tooltip("payer:N", title="User"),
                alt.Tooltip("Company:N", title="Company"),
                alt.Tooltip("Value:Q", title=agg_type),
            ],
        )
        .properties(height=30 * len(pivot), width=700)
    )
    st.altair_chart(heatmap, use_container_width=True)

    # ───────────────────────────────────────────
    # 6) RFM + Churn Metrics
    # ───────────────────────────────────────────
    tips["date"] = pd.to_datetime(tips["date"], errors="coerce")
    today = pd.to_datetime("today").normalize()

    # a) per-user summary
    rfm = (
        tips.groupby("payer")
            .agg(
                FirstTip   = ("date", "min"),
                LastTip    = ("date", "max"),
                Frequency  = ("uuid", "count"),
                Monetary   = ("amount", "sum"),
                Companies  = ("company", pd.Series.nunique),
                ActiveDays = ("date", lambda s: s.dt.date.nunique())
            )
            .reset_index()
    )
    rfm["Recency"]  = (today - rfm["LastTip"]).dt.days
    rfm["Lifespan"] = (rfm["LastTip"] - rfm["FirstTip"]).dt.days

    # b) определяем churn threshold
    churn_thresh = st.slider(
        "Churn threshold (days since last tip)", 
        min_value=1, max_value=90, value=30, step=1
    )
    rfm["Churned"] = rfm["Recency"] > churn_thresh

    # c) KPI
    total_users   = len(rfm)
    new_users     = rfm[rfm["FirstTip"] >= (today - pd.Timedelta(days=churn_thresh))].shape[0]
    churned_users = rfm["Churned"].sum()
    retained      = total_users - churned_users

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total users",       total_users)
    c2.metric(f"New last {churn_thresh}d", new_users)
    c3.metric(f"Churned (> {churn_thresh}d)", churned_users)
    c4.metric("Retention rate",     f"{retained/total_users:.0%}")

    # d) Детальная таблица RFM & Churn
    with st.expander("RFM & Churn detail", expanded=False):
        st.dataframe(
            rfm[[
                "payer","Recency","Frequency","Monetary",
                "Companies","ActiveDays","Lifespan","Churned"
            ]]
            .sort_values("Recency", ascending=False)
            .reset_index(drop=True),
            use_container_width=True
        )

    # e) Weekly New vs Churned
    weekly = (
        rfm
        .assign(Week=lambda d: d["FirstTip"].dt.to_period("W").apply(lambda r: r.start_time))
        .groupby("Week")
        .apply(
            lambda grp: pd.Series({
                "NewUsers": grp.loc[
                    grp["FirstTip"] >= (today - pd.Timedelta(days=churn_thresh)),
                    "payer"
                ].nunique(),
                "Churned": grp.loc[grp["Churned"], "payer"].nunique()
            })
        )
        .reset_index()
    )
    if not weekly.empty:
        chart = (
            alt.Chart(weekly.melt("Week", var_name="Metric", value_name="Count"))
            .mark_bar()
            .encode(
                x=alt.X("Week:T", title="Week"),
                y=alt.Y("Count:Q", title="Users"),
                color=alt.Color("Metric:N", title="Metric"),
                tooltip=["Week:T","Metric:N","Count:Q"]
            )
            .properties(height=200)
            .configure_axis(labelColor="white", titleColor="white")
        )
        st.altair_chart(chart, use_container_width=True)

    # ───────────────────────────────────────────
    # 7) Download pivot as Excel
    # ───────────────────────────────────────────
    with st.expander("Download pivot as Excel"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            pivot.to_excel(writer, sheet_name="UsersTips")
        data = buffer.getvalue()
        st.download_button(
            "Download pivot as Excel",
            data=data,
            file_name="users_tips_pivot.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
