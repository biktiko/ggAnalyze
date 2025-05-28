import streamlit as st
import altair as alt
import pandas as pd
import numpy as np
import datetime

def show(data: dict | None = None) -> None:
    """
    Вкладка «Companies Activations»: изменение активности компаний в очках
    между двумя срезами (половина периода или пользовательский Custom).
    Очки считаются по формуле из Top Companies, затем делятся на длину периода.
    """
    st.subheader("Companies Activations")

    # 1) Исходные данные
    companies = data.get("ggtipsCompanies", pd.DataFrame()).copy()
    tips       = data.get("ggtips", pd.DataFrame()).copy()
    teammates  = data.get("ggTeammates", pd.DataFrame())

    if companies.empty or tips.empty:
        st.info("No data for Companies Activations yet.")
        return

    # 2) Проверка столбцов
    for col in ["company", "days"]:
        if col not in companies.columns:
            st.warning(f"Companies data must contain '{col}' column.")
            return

    # 3) Подготовка act_days
    act_days = (
        companies[["company", "days"]]
            .dropna(subset=["company", "days"])
            .rename(columns={"company": "Company", "days": "Days"})
            .drop_duplicates(subset=["Company"], keep="first")
    )

    # 4) UI — настройки
    with st.expander("Config", expanded=True):

        st1, st2 = st.columns(2)

        with st1:
            format_option = st.selectbox(
                "Different format", ["Numbers", "Percentage"], key="act_format_option"
            )

        with st2:
            period_format = st.selectbox(
                "Period format", ["Half", "Custom"], key="act_period_format"
            )

        # Custom: два диапазона дат в двух колонках
        if period_format == "Custom":
            today = datetime.date.today()
            default_end2 = today
            default_start2 = today - datetime.timedelta(days=7)
            default_end1 = default_start2
            default_start1 = default_start2 - datetime.timedelta(days=7)

            col1, col2 = st.columns(2)
            with col1:
                period1 = st.date_input(
                    "Period A", value=(default_start1, default_end1), key="p1_range"
                )
            with col2:
                period2 = st.date_input(
                    "Period B", value=(default_start2, default_end2), key="p2_range"
                )
            p1_start, p1_end = period1
            p2_start, p2_end = period2
        else:
            p1_start = p1_end = p2_start = p2_end = None

        plot_threshold = st.number_input(
            "Max abs diff for plot",
            min_value=0.0, value=5.0, step=1.0,
            help="Все значения > ±threshold будут обрезаны до ±threshold",
            key="act_plot_threshold"
        )

    # 5) Фильтрация tips
    tips_clean = tips.copy()
    if "ggPayer" in tips_clean.columns and "id" in teammates.columns:
        tips_clean = tips_clean[~tips_clean["ggPayer"].isin(teammates["id"])]
    if "status" in tips_clean.columns:
        tips_clean = tips_clean[tips_clean["status"] == "finished"]
    if "date" in tips_clean.columns:
        tips_clean["date"] = pd.to_datetime(tips_clean["date"], errors="coerce")
    else:
        st.warning("Tips data must contain 'date' column.")
        return

    # 6) Join с act_days
    merged = tips_clean.merge(
        act_days, left_on="company", right_on="Company", how="inner"
    )
    if merged.empty:
        st.info("No tips matching companies with active days.")
        return

    # 7) Рассчет периодов
    if period_format == "Half":
        today_pd = pd.to_datetime("today").normalize()
        act_days = act_days.assign(
            Len_first=act_days["Days"]/2,
            Len_second=act_days["Days"]/2
        )
        act_days["threshold"] = today_pd - pd.to_timedelta(
            act_days["Len_second"], unit="D"
        )
        merged = merged.merge(
            act_days[["Company", "Len_first", "Len_second", "threshold"]],
            on="Company", how="left"
        )
        first_df = merged[merged["date"] < merged["threshold"]]
        second_df = merged[merged["date"] >= merged["threshold"]]
    else:
        diff1 = max((pd.to_datetime(p1_end) - pd.to_datetime(p1_start)).days, 1)
        diff2 = max((pd.to_datetime(p2_end) - pd.to_datetime(p2_start)).days, 1)
        act_days = act_days.assign(
            Len_first=diff1,
            Len_second=diff2
        )
        merged = merged.merge(
            act_days[["Company", "Len_first", "Len_second"]],
            on="Company", how="left"
        )
        first_df = merged[
            (merged["date"] >= pd.to_datetime(p1_start)) &
            (merged["date"] <= pd.to_datetime(p1_end))
        ]
        second_df = merged[
            (merged["date"] >= pd.to_datetime(p2_start)) &
            (merged["date"] <= pd.to_datetime(p2_end))
        ]

    # 8) Агрегация
    grp1 = first_df.groupby("Company", observed=True).agg(
        Amount_first=("amount", "sum"),
        Count_first=("uuid", "count")
    )
    grp2 = second_df.groupby("Company", observed=True).agg(
        Amount_second=("amount", "sum"),
        Count_second=("uuid", "count")
    )
    base_df = pd.merge(
        grp1, grp2, left_index=True, right_index=True, how="outer"
    ).fillna(0).reset_index()

    # 9) Merge с длинами
    df = base_df.merge(
        act_days[["Company", "Len_first", "Len_second"]],
        on="Company", how="left"
    )

    # 10) Расчет Scope
    one_avg_tip = tips_clean["amount"].mean() or 1
    df["Scope_first"] = (
        ((df["Amount_first"]/one_avg_tip) + df["Count_first"]) / 2
    ) / df["Len_first"]
    df["Scope_second"] = (
        ((df["Amount_second"]/one_avg_tip) + df["Count_second"]) / 2
    ) / df["Len_second"]
    df[["Scope_first", "Scope_second"]] = df[[
        "Scope_first", "Scope_second"
    ]].round(2)

    # 11) Дельты и отображение
    df["DiffNum"] = (df["Scope_second"] - df["Scope_first"]).round(2)
    df["DiffPercent"] = ((
        df["DiffNum"]/df["Scope_first"].replace(0, np.nan)
    ) * 100).fillna(-100).round(2)

    diff_col = "DiffNum" if format_option == "Numbers" else "DiffPercent"
    df["DiffPlot"] = df[diff_col].clip(
        lower=-plot_threshold, upper=plot_threshold
    )

    df = df.sort_values(diff_col, ascending=False, ignore_index=True)
    order = df["Company"].tolist()

    chart = alt.Chart(df).encode(
        y=alt.Y("Company:N", sort=order, axis=alt.Axis(title="Company")),
        tooltip=[
            "Company",
            alt.Tooltip("Scope_first:Q", title="Scope 1", format=".2f"),
            alt.Tooltip("Scope_second:Q", title="Scope 2", format=".2f"),
            alt.Tooltip(f"{diff_col}:Q", title=diff_col, format=".2f"),
            "Len_first", "Len_second"
        ]
    ).mark_bar().encode(
        x=alt.X(
            "DiffPlot:Q", axis=alt.Axis(title="Δ Scope"),
            scale=alt.Scale(domain=[-plot_threshold, plot_threshold])
        ),
        color=alt.condition(
            alt.datum[diff_col] >= 0, alt.value("green"), alt.value("red")
        )
    )

    total_diff = df["DiffNum"].sum()
    avg_diff = df["DiffNum"].mean().round(2)

    with st.expander("Overall Summary", expanded=False):
        if total_diff > 0:
            st.markdown(
                f"Overall, companies have become **more active** by a total of {total_diff:.2f} points "
                f"(average change per company {avg_diff:+.2f})."
            )
        elif total_diff < 0:
            st.markdown(
                f"Overall, companies have become **less active** by a total of {abs(total_diff):.2f} points "
                f"(average change per company {avg_diff:+.2f})."
            )
        else:
            st.markdown("**Overall, there are no changes** (average change per company 0.00).")


    st.altair_chart(
        chart.resolve_scale(x="shared").configure_axis(
            labelColor="white", titleColor="white"
        ), use_container_width=True
    )

    # 12) Таблицы
    with st.expander("Details", expanded=False):
        st.dataframe(df)
        st.dataframe(
            df[["Company", "Scope_first", "Scope_second", "DiffNum", "DiffPercent"]],
            use_container_width=True
        )