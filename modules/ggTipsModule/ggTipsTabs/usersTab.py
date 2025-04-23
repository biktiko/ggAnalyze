# modules/ggTipsModule/ggTipsTabs/usersTab.py

import io
import streamlit as st
import pandas as pd
import altair as alt

def show(data: dict | None = None) -> None:
    """
    Вкладка «Users» — сводная таблица и тепловая карта,
    показывающие, сколько чаевых (Count или Amount) оставил каждый пользователь в каждой компании.
    """
    st.subheader("Users Tip Distribution")

    tips = data.get("ggtips", pd.DataFrame()).copy()
    if tips.empty:
        st.info("No tips data to show.")
        return

    # ─── 1) Панель настроек ─────────────────────────────────────────────────────
    with st.expander("Config", expanded=True):
        agg_type = st.selectbox("Value type", ["Count", "Amount"])
        top_n    = st.number_input(
            "Top N users to display", min_value=1, value=15, step=1
        )
        thresh = st.slider(
            "Minimum total per user",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            help="Скрыть пользователей с суммой/count ниже этого порога"
        )

    # ─── 2) Готовим pivot-таблицу ───────────────────────────────────────────────
    pivot = pd.pivot_table(
        tips,
        index="payer",
        columns="company",
        values="amount",
        aggfunc="count" if agg_type == "Count" else "sum",
        fill_value=0,
    )

    # Фильтруем по порогу, сортируем и берём top_n
    pivot["__Total"] = pivot.sum(axis=1)
    pivot = pivot[pivot["__Total"] >= thresh]
    pivot = pivot.sort_values("__Total", ascending=False).head(top_n)
    pivot = pivot.drop(columns="__Total")

    # ─── 3) Показываем таблицу ─────────────────────────────────────────────────
    st.write(
        f"Showing top {len(pivot)} users ({agg_type}), "
        f"threshold ≥ {thresh:.0f}"
    )
    st.dataframe(pivot, use_container_width=True)

    # ─── 4) Рисуем тепловую карту с Altair ──────────────────────────────────────
    df_heat = (
        pivot
        .reset_index()
        .melt(id_vars="payer", var_name="Company", value_name="Value")
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
        .properties(
            height=30 * len(pivot),  # 30px на каждую строку
            width=700
        )
    )
    st.altair_chart(heatmap, use_container_width=True)

    # ─── 5) Скачивание в Excel ─────────────────────────────────────────────────
    with st.expander("Download as Excel"):
        to_download = pivot.copy()
        to_download.index.name = "payer"

        # Записываем DataFrame в буфер
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            to_download.to_excel(writer, sheet_name="UsersTips")
        data = buffer.getvalue()

        st.download_button(
            "Download pivot as Excel",
            data=data,
            file_name="users_tips_pivot.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
