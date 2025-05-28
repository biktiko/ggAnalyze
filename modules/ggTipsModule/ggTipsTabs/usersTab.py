# modules/ggTipsModule/ggTipsTabs/usersTab.py

import io
import streamlit as st
import pandas as pd
import altair as alt

def show(data: dict | None = None) -> None:
    st.subheader("Users Tip Distribution")

    # ─── 1) Исходные данные ─────────────────────────────────────────────────────
    tips = data.get("ggtips", pd.DataFrame()).copy()
    if tips.empty:
        st.info("Нет данных по чаевым.")
        return
    tips["date"] = pd.to_datetime(tips["date"], errors="coerce")
    tips = tips.dropna(subset=["payer", "date", "uuid"])
    today = pd.to_datetime("today").normalize()

    # ─── 2) Pivot & Heatmap Config ──────────────────────────────────────────────

    with st.expander("Config pivot & heatmap", expanded=True):
        agg_type    = st.selectbox("Value type", ["Count", "Amount"])
        top_n       = st.number_input("Top N users to display", 1, 10000, 100)
        thresh      = st.number_input("Min total per user",
                                      min_value=0.0,
                                      max_value=float(tips["amount"].max()),
                                      value=0.0)


    # ─── 3) Pivot-таблица ───────────────────────────────────────────────────────
    with st.expander("Pivot table", expanded=True):
        pivot = pd.pivot_table(
            tips,
            index="payer",
            columns="company",
            values="amount",
            aggfunc="count" if agg_type=="Count" else "sum",
            fill_value=0
        )
        pivot["__Total"] = pivot.sum(axis=1)
        pivot = (
            pivot[pivot["__Total"] >= thresh]
                .sort_values("__Total", ascending=False)
                .head(top_n)
                .drop(columns="__Total")
        )
        st.write(f"Top {len(pivot)} users ({agg_type}), ≥{thresh:.0f}")
        st.dataframe(pivot, use_container_width=True)

        df_heat = pivot.reset_index().melt("payer", var_name="Company", value_name="Value")
        heatmap = (
            alt.Chart(df_heat)
            .mark_rect()
            .encode(
                x="Company:N",
                y=alt.Y("payer:O", sort=pivot.index.astype(str).tolist()),
                color=alt.Color(
                    "Value:Q",
                    scale=alt.Scale(
                        range=["#ffffff", "#00008b"]  # от чисто-белого до тёмно-синего
                    ),
                    legend=alt.Legend(title=agg_type)
                ),
                tooltip=["payer:N", "Company:N", "Value:Q"]
            )
            .properties(height=30 * len(pivot), width=700)
        )

        st.altair_chart(heatmap, use_container_width=True)

    # ─── 4) Настройки «регулярности» ─────────────────────────────────────────────
    with st.expander("Config activity metrics", expanded=True):
        period_thresh = st.number_input(
            "Max gap between unique tip-days (days)",
            min_value=1, max_value=60, value=7
        )
        min_tips = st.number_input(
            "Min unique tip-days to qualify",
            min_value=2, max_value=100, value=3
        )

    # ─── 5) RFM-подобная таблица ────────────────────────────────────────────────
    rfm = (
        tips.groupby("payer")
            .agg(
                FirstTip   = ("date","min"),
                LastTip    = ("date","max"),
                Count      = ("uuid","count"),
                Amount     = ("amount","sum"),
                Companies  = ("company",pd.Series.nunique),
                ActiveDays = ("date", lambda s: s.dt.date.nunique()),
            )
            .reset_index()
    )
    rfm["Lifespan"] = (rfm["LastTip"] - rfm["FirstTip"]).dt.days

    # ─── 6) Уникальные дни и дата «становления регулярным» ─────────────────────
    uniq = ( 
        tips.assign(day=tips["date"].dt.normalize())
            .drop_duplicates(subset=["payer","day"])
            .sort_values(["payer","day"])
            .groupby("payer")["day"]
            .apply(list)
            .reset_index(name="days_list")
    )

    def find_regular_start(days, gap, mind):
        if len(days) < mind:
            return pd.NaT
        for i in range(mind, len(days)+1):
            seq = days[:i]
            diffs = [(seq[j] - seq[j-1]).days for j in range(1,len(seq))]
            if max(diffs) <= gap:
                return seq[-1]
        return pd.NaT

    uniq["RegularSince"] = uniq["days_list"].apply(
        lambda d: find_regular_start(d, period_thresh, min_tips)
    )
    qualifiers = uniq.dropna(subset=["RegularSince"]).copy()

    # ─── 7) Флаг «Ongoing» ──────────────────────────────────────────────────────
    qualifiers = qualifiers.merge(
        rfm[["payer","LastTip"]], on="payer", how="left"
    )
    qualifiers["Ongoing"] = (today - qualifiers["LastTip"]).dt.days <= period_thresh

    # ─── 8) KPI ─────────────────────────────────────────────────────────────────
    total_users   = tips["payer"].nunique()
    ever_reg      = qualifiers["payer"].nunique()
    ongoing_reg   = qualifiers.loc[qualifiers["Ongoing"], "payer"].nunique()
    stale_users   = total_users - ever_reg

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total users", total_users)
    c2.metric(f"EverRegular (≥{min_tips} days)", ever_reg)
    c3.metric(f"OngoingRegular (gap≤{period_thresh})", ongoing_reg)
    c4.metric("Stale users", stale_users)

    # ─── 9) Детальная таблица «User detail» с периодичностью и фильтрами ─────────
    with st.expander("User detail & filters", expanded=False):
        # 1) Собираем базовый df
        df_detail = (
            rfm
            .merge(qualifiers[["payer", "RegularSince", "Ongoing"]], on="payer", how="left")
        )

        # 2) Добавляем средний период между уникальными днями чаевых
        gaps_summary = (
            tips.assign(day=tips["date"].dt.normalize())
                .drop_duplicates(subset=["payer","day"])
                .sort_values(["payer","day"])
                .groupby("payer")["day"]
                .apply(list)
                .reset_index(name="days_list")
        )
        def avg_gap(days):
            if len(days) < 2:
                return None
            ds = sorted(days)
            diffs = [(ds[i] - ds[i-1]).days for i in range(1, len(ds))]
            return sum(diffs) / len(diffs)
        gaps_summary["Periodicity"] = gaps_summary["days_list"].apply(avg_gap)

        df_detail = df_detail.merge(
            gaps_summary[["payer","Periodicity"]],
            on="payer", how="left"
        )

        # 3) Переименовываем колонки
        df_detail = df_detail.rename(columns={
            "FirstTip":      "First tip",
            "LastTip":       "Last tip",
            "Count":         "Count",
            "Amount":        "Amount",
            "Companies":     "Companies",
            "ActiveDays":    "Active days",
            "Lifespan":      "Lifespan",
            "RegularSince":  "Regular since",
            "Periodicity":   "Avg period (days)",
            "Ongoing":       "Ongoing"
        })[
            [
                "payer","First tip","Last tip","Count","Amount","Companies",
                "Active days","Lifespan","Avg period (days)","Regular since","Ongoing"
            ]
        ]

        # 4) Интерфейс для фильтрации по всем столбцам
        st.markdown("#### Filters")
        c1, c2, c3 = st.columns(3)
        with c1:
            ft_min, ft_max = st.date_input(
                "First tip range",
                value=(df_detail["First tip"].min(), df_detail["First tip"].max())
            )
            cnt_min, cnt_max = st.slider(
                "Count range",
                int(df_detail["Count"].min()), int(df_detail["Count"].max()),
                (int(df_detail["Count"].min()), int(df_detail["Count"].max()))
            )
        with c2:
            lt_min, lt_max = st.date_input(
                "Last tip range",
                value=(df_detail["Last tip"].min(), df_detail["Last tip"].max())
            )
            # ← Заменили number_input на slider для диапазона
            amt_min, amt_max = st.slider(
                "Amount range",
                float(df_detail["Amount"].min()), float(df_detail["Amount"].max()),
                (float(df_detail["Amount"].min()), float(df_detail["Amount"].max()))
            )
        with c3:
            per_min, per_max = st.slider(
                "Avg period (days)",
                float(df_detail["Avg period (days)"].min()), float(df_detail["Avg period (days)"].max()),
                (float(df_detail["Avg period (days)"].min()), float(df_detail["Avg period (days)"].max()))
            )
            ls_min, ls_max = st.slider(
                "Lifespan (days)",
                int(df_detail["Lifespan"].min()), int(df_detail["Lifespan"].max()),
                (int(df_detail["Lifespan"].min()), int(df_detail["Lifespan"].max()))
            )


        # 5) Применяем фильтр
        mask = (
            (df_detail["First tip"] >= pd.to_datetime(ft_min)) &
            (df_detail["First tip"] <= pd.to_datetime(ft_max)) &
            (df_detail["Last tip"]  >= pd.to_datetime(lt_min)) &
            (df_detail["Last tip"]  <= pd.to_datetime(lt_max)) &
            (df_detail["Count"].between(cnt_min, cnt_max)) &
            (df_detail["Amount"].between(amt_min, amt_max)) &
            (df_detail["Avg period (days)"].between(per_min, per_max)) &
            (df_detail["Lifespan"].between(ls_min, ls_max))
        )
        st.dataframe(df_detail[mask].reset_index(drop=True), use_container_width=True)

    # ─── 10) Еженедельные метрики ───────────────────────────────────────────────
    new_week = (
        rfm.dropna(subset=["FirstTip"])
           .assign(Week=lambda df: df["FirstTip"].dt.to_period("W").dt.start_time)
           .groupby("Week")["payer"].nunique()
           .reset_index(name="NewUsers")
    )
    new_reg = (
        qualifiers
        .assign(Week=lambda df: df["RegularSince"].dt.to_period("W").dt.start_time)
        .groupby("Week")["payer"].nunique()
        .reset_index(name="NewRegularUsers")
    )
    new_ongoing = (
        qualifiers[qualifiers["Ongoing"]]
        .assign(Week=lambda df: df["RegularSince"].dt.to_period("W").dt.start_time)
        .groupby("Week")["payer"].nunique()
        .reset_index(name="NewOngoingRegularUsers")
    )

    plot_df = (
        new_week
        .merge(new_reg,     on="Week", how="outer")
        .merge(new_ongoing, on="Week", how="outer")
        .fillna(0)
        .sort_values("Week")
    )

    # ─── 11) Weekly counts ─────────────────────────────────────────────────────
    st.markdown("### Weekly counts")
    bar = (
        alt.Chart(plot_df.melt(
            id_vars="Week",
            value_vars=["NewUsers","NewRegularUsers","NewOngoingRegularUsers"],
            var_name="Metric", value_name="Users"
        ))
        .mark_bar()
        .encode(
            x="Week:T", y="Users:Q",
            color=alt.Color("Metric:N",
                scale=alt.Scale(
                    domain=["NewUsers","NewRegularUsers","NewOngoingRegularUsers"],
                    range=["#1f77b4","#0000FF","#9467bd"]
                )
            ),
            tooltip=["Week:T","Metric:N","Users:Q"]
        )
        .properties(height=300)
    )
    st.altair_chart(bar, use_container_width=True)

    # ─── 12) Tabs: регулярность по неделям, месяцам и за весь период ───────────
    tab_w, tab_mo, tab_all = st.tabs(["Weekly %", "Monthly %", "All time %"])

    # --- Weekly % tab ---
    with tab_w:
        df_w = plot_df.assign(
            PctNewRegular = (plot_df["NewRegularUsers"]/plot_df["NewUsers"]).fillna(0)*100,
            PctNewOngoing = (plot_df["NewOngoingRegularUsers"]/plot_df["NewUsers"]).fillna(0)*100
        ).melt(
            id_vars="Week",
            value_vars=["PctNewRegular","PctNewOngoing"],
            var_name="Metric", value_name="Percent"
        )
        chart_w = (
            alt.Chart(df_w)
            .mark_line(point=True, strokeWidth=3)
            .encode(
                x="Week:T",
                y=alt.Y("Percent:Q", title="% of new users"),
                color=alt.Color("Metric:N",
                                scale=alt.Scale(
                                    domain=["PctNewRegular","PctNewOngoing"],
                                    range=["#0000FF","#9467bd"]
                                ),
                                legend=alt.Legend(title="Metric",
                                                  labelExpr=
                                                  "datum.value=='PctNewRegular'? 'New→Regular':'New→Ongoing'")
                ),
                tooltip=["Week:T","Metric:N","Percent:Q"]
            )
            .properties(height=300)
        )
        st.altair_chart(chart_w, use_container_width=True)

    # --- Monthly % tab ---
    with tab_mo:
        # аналогичные вычисления по месяцам
        mo_new = new_week.assign(Month=lambda df: df["Week"].dt.to_period("M").dt.start_time)\
                         .groupby("Month")["NewUsers"].sum().reset_index()
        mo_reg = new_reg.assign(Month=lambda df: df["Week"].dt.to_period("M").dt.start_time)\
                        .groupby("Month")["NewRegularUsers"].sum().reset_index()
        mo_ongo = new_ongoing.assign(Month=lambda df: df["Week"].dt.to_period("M").dt.start_time)\
                              .groupby("Month")["NewOngoingRegularUsers"].sum().reset_index()

        df_m = (
            mo_new.merge(mo_reg, on="Month", how="outer")
                  .merge(mo_ongo, on="Month", how="outer")
                  .fillna(0)
                  .sort_values("Month")
        )
        df_m = df_m.assign(
            PctNewRegular=(df_m["NewRegularUsers"]/df_m["NewUsers"]).fillna(0)*100,
            PctNewOngoing=(df_m["NewOngoingRegularUsers"]/df_m["NewUsers"]).fillna(0)*100
        ).melt(
            id_vars="Month",
            value_vars=["PctNewRegular","PctNewOngoing"],
            var_name="Metric", value_name="Percent"
        )
        chart_m = (
            alt.Chart(df_m)
            .mark_line(point=True, strokeWidth=3)
            .encode(
                x="Month:T",
                y=alt.Y("Percent:Q", title="% of new users"),
                color=alt.Color("Metric:N",
                                scale=alt.Scale(
                                    domain=["PctNewRegular","PctNewOngoing"],
                                    range=["#0000FF","#9467bd"]
                                )),
                tooltip=["Month:T","Metric:N","Percent:Q"]
            )
            .properties(height=300)
        )
        st.altair_chart(chart_m, use_container_width=True)

        # --- All time % tab: Funnel New → EverRegular → OngoingRegular ---
    with tab_all:
        # Готовим данные для воронки
        df_funnel = pd.DataFrame({
            "Stage": ["New users", "Ever regular", "Ongoing regular"],
            "Count": [total_users, ever_reg, ongoing_reg]
        })

        funnel = (
            alt.Chart(df_funnel)
            .mark_bar()
            .encode(
                y=alt.Y("Stage:N",
                        sort=["New users", "Ever regular", "Ongoing regular"],
                        title=None),
                x=alt.X("Count:Q", title="Users"),
                color=alt.Color("Stage:N",
                                scale=alt.Scale(
                                    domain=["New users", "Ever regular", "Ongoing regular"],
                                    range=["#1f77b4", "#0000FF", "#9467bd"]
                                ),
                                legend=None),
                tooltip=[alt.Tooltip("Stage:N", title="Stage"),
                         alt.Tooltip("Count:Q", title="Users")]
            )
            .properties(height=200)
        )
        st.altair_chart(funnel, use_container_width=True)


    # ─── 13) User IDs by week ─────────────────────────────────────────────────
    tips_w = (
        tips.assign(Week=lambda df: df["date"].dt.to_period("W").dt.start_time)
            .drop_duplicates(subset=["payer","Week"])
    )
    new_ids = (
        tips_w.merge(rfm[["payer","FirstTip"]], on="payer")
              .assign(FirstWeek=lambda df: df["FirstTip"].dt.to_period("W").dt.start_time)
              .query("Week == FirstWeek")
              .groupby("Week")["payer"].apply(list)
              .reset_index(name="NewUserIDs")
    )
    new_reg_ids = (
        qualifiers
        .assign(Week=lambda df: df["RegularSince"].dt.to_period("W").dt.start_time)
        .groupby("Week")["payer"].apply(list)
        .reset_index(name="NewRegularUserIDs")
    )
    new_ongoing_ids = (
        qualifiers[qualifiers["Ongoing"]]
        .assign(Week=lambda df: df["RegularSince"].dt.to_period("W").dt.start_time)
        .groupby("Week")["payer"].apply(list)
        .reset_index(name="NewOngoingRegularUserIDs")
    )
    week_ids = (
        new_ids
        .merge(new_reg_ids,     on="Week", how="outer")
        .merge(new_ongoing_ids, on="Week", how="outer")
        .sort_values("Week")
    )
    st.subheader("User IDs by week")
    st.dataframe(week_ids, use_container_width=True)

    # ─── 14) Download pivot as Excel ───────────────────────────────────────────
    with st.expander("Download pivot as Excel"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as wr:
            pivot.to_excel(wr, sheet_name="UsersTips")
        st.download_button(
            "Download pivot as Excel",
            data=buf.getvalue(),
            file_name="users_tips_pivot.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
