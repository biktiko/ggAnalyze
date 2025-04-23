# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\modules\ggTipsModule\ggTipsTabs\companyActivations.py

import streamlit as st
import altair as alt
import pandas as pd
import numpy as np

def show(data: dict | None = None) -> None:
    """
    Вкладка «Companies Activations»: изменение активности компаний в очках
    между двумя срезами (половина периода или пользовательский Custom).
    Очки считаются по формуле из Top Companies, затем делятся на длину периода.
    """
    st.subheader("Companies Activations")

    # 1) Исходные данные
    companies = data.get("ggtipsCompanies", pd.DataFrame()).copy()
    tips       = data.get("ggtips",         pd.DataFrame()).copy()
    teammates  = data.get("ggTeammates",    pd.DataFrame())

    if companies.empty or tips.empty:
        st.info("No data for Companies Activations yet.")
        return

    # 2) Таблица «дней активности» компании
    if "company" not in companies.columns or "days" not in companies.columns:
        st.warning("Companies data must contain 'company' and 'days' columns.")
        return

    act_days = (
        companies[["company","days"]]
            .dropna(subset=["company","days"])
            .rename(columns={"company":"Company","days":"Days"})
            .drop_duplicates(subset=["Company"], keep="first")
    )

    # 3) UI — настройки
    with st.expander("Config", expanded=True):
        format_option = st.selectbox(
            "Different format", ["Numbers","Percentage"], key="act_format_option"
        )
        period_format = st.selectbox(
            "Period format", ["Half","Custom"], key="act_period_format"
        )
        custom_days = None
        if period_format == "Custom":
            custom_days = st.number_input(
                "Custom period (days)",
                min_value=1, value=7, step=1,
                key="act_period_days"
            )
        plot_threshold = st.number_input(
            "Max abs diff for plot",
            min_value=0.0, value=5.0, step=1.0,
            help="Все значения > ±threshold будут обрезаны до ±threshold"
        )

    # 4) отсекаем компании с малоактивными днями
    if period_format == "Custom":
        act_days = act_days[act_days["Days"] > custom_days]
        if act_days.empty:
            st.info("No companies with Days > custom period.")
            return

    # 5) фильтруем транзакции
    tips_clean = tips.copy()
    if "ggPayer" in tips_clean.columns and "id" in teammates.columns:
        tips_clean = tips_clean[~tips_clean["ggPayer"].isin(teammates["id"])]
    if "status" in tips_clean.columns:
        tips_clean = tips_clean[tips_clean["status"]=="finished"]
    if "date" in tips_clean.columns:
        tips_clean["date"] = pd.to_datetime(tips_clean["date"], errors="coerce")
    else:
        st.warning("Tips data must contain 'date' column.")
        return

    # 6) джоин с днями активности
    merged = tips_clean.merge(
        act_days, left_on="company", right_on="Company", how="inner"
    )
    if merged.empty:
        st.info("No tips matching companies with active days.")
        return

    # 7) рассчитываем длины первого и второго периода и порог
    today = pd.to_datetime("today").normalize()

    if period_format == "Half":
        # оба периода — Days/2
        act_days = act_days.assign(
            Len_first = act_days["Days"]/2,
            Len_second= act_days["Days"]/2
        )
    else:
        # первый = Days - custom_days, второй = custom_days
        act_days = act_days.assign(
            Len_second= custom_days,
            Len_first = act_days["Days"] - custom_days
        )

    # пороговая зачерпывающая дата
    act_days["threshold"] = today - pd.to_timedelta(act_days["Len_second"], unit="D")

    # 8) объединяем с merged
    merged = merged.merge(
        act_days[["Company","Days","Len_first","Len_second","threshold"]],
        on="Company", how="left"
    )

    # 9) делим на два среза
    first_df  = merged[merged["date"] <  merged["threshold"]]
    second_df = merged[merged["date"] >= merged["threshold"]]

    # 10) агрегация
    grp1 = first_df.groupby("Company", observed=True).agg(
        Amount_first = ("amount","sum"),
        Count_first  = ("uuid","count")
    )
    grp2 = second_df.groupby("Company", observed=True).agg(
        Amount_second= ("amount","sum"),
        Count_second = ("uuid","count")
    )
    base_df = pd.merge(grp1, grp2, left_index=True, right_index=True, how="outer").fillna(0).reset_index()

    # 11) финальный merge с длинами и днями
    df = base_df.merge(
        act_days[["Company","Days","Len_first","Len_second"]],
        on="Company", how="left"
    )

    # 12) считаем очки (Scope) по формуле Top Companies и нормируем на длину периода
    one_avg_tip = tips_clean["amount"].mean() or 1
    df["Scope_first"]  = (
        ((df["Amount_first"]/one_avg_tip) + df["Count_first"]) / 2
    ) / df["Len_first"]
    df["Scope_second"] = (
        ((df["Amount_second"]/one_avg_tip) + df["Count_second"]) / 2
    ) / df["Len_second"]
    df["Scope_first"]  = df["Scope_first"].round(2)
    df["Scope_second"] = df["Scope_second"].round(2)

    # 13) дельты
    df["DiffNum"]     = (df["Scope_second"] - df["Scope_first"]).round(2)
    df["DiffPercent"] = (
        (df["DiffNum"] / df["Scope_first"].replace(0, np.nan)) * 100
    ).fillna(-100).round(2)

    diff_col = "DiffNum" if format_option=="Numbers" else "DiffPercent"
    df["DiffPlot"] = df[diff_col].clip(lower=-plot_threshold, upper=plot_threshold)

    # 14) сортировка
    df = df.sort_values(diff_col, ascending=False, ignore_index=True)

    # 15) отрисовка горизонтального бартчарта
    order = df["Company"].tolist()
    base = alt.Chart(df).encode(
        y=alt.Y("Company:N", sort=order, axis=alt.Axis(title="Company")),
        tooltip=[
            "Company",
            alt.Tooltip("Scope_first:Q",  format=".2f", title="Scope 1"),
            alt.Tooltip("Scope_second:Q", format=".2f", title="Scope 2"),
            alt.Tooltip(f"{diff_col}:Q",   format=".2f", title=diff_col),
            "Days"
        ]
    )
    bars = base.mark_bar().encode(
        x=alt.X(
            "DiffPlot:Q",
            axis=alt.Axis(title="Δ Scope"),
            scale=alt.Scale(domain=[-plot_threshold, plot_threshold])
        ),
        color=alt.condition(
            alt.datum[diff_col]>=0, alt.value("green"), alt.value("red")
        )
    )
    st.altair_chart(
        bars.resolve_scale(x="shared").configure_axis(
            labelColor="white", titleColor="white"
        ),
        use_container_width=True
    )

    st.write(df)

    # 16) подробная таблица
    with st.expander("Details", expanded=False):
        st.dataframe(
            df[[
                "Company","Scope_first","Scope_second","DiffNum","DiffPercent","Days"
            ]],
            use_container_width=True
        )
