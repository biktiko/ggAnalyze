import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import io

def show(data: dict,) -> None:
    """
    Tab "Orders" — daily analytics of company orders.
    Accepts:
      - data: {"orders": DataFrame, "clients": DataFrame, "cancellations": DataFrame, "users": DataFrame}
    """
    st.subheader("Daily Orders per Company")

    # --- Filters (Moved from sidebar to main page) ---
    with st.expander("Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            min_avg = st.number_input('Min. avg orders per day', 0.0, None, 1.0, 0.1)
            last_days = st.number_input('Companies joined in last N days', 0, None, 7)
        with col2:
            today = datetime.today().date()
            default_start = today - timedelta(days=30)
            date_range = st.date_input('Date range for table', value=(default_start, today))
        with col3:
            include_weekends = st.checkbox('Include weekends', value=True)
            # This checkbox will control the visibility of the Excel download button later
            download_excel_check = st.checkbox('Prepare Excel for download')

    # --- Data Loading and Preparation ---
    orders = data.get("orders", pd.DataFrame()).copy()
    clients = data.get("clients", pd.DataFrame()).copy()
    cancels = data.get("cancellations", pd.DataFrame()).copy()
    users_df = data.get("users", pd.DataFrame()).copy()
    if orders.empty or clients.empty:
        st.info("Not enough data: please provide both 'orders' and 'clients' data.")
        return

    # Prepare dates and types
    orders["date"] = pd.to_datetime(orders["date"], errors="coerce").dt.date
    clients["userid"] = clients["userid"].astype(str)
    clients["mobile"] = clients["mobile"].astype(str)
    clients["companymanager"] = clients["companymanager"].astype(str)
    clients["join_date"] = pd.to_datetime(clients.get("date"), errors="coerce").dt.date

    # Prepare cancels and map to companies
    if not cancels.empty and not users_df.empty:
        import ast
        def parse_list(val):
            try:
                return [int(x) for x in ast.literal_eval(str(val))]
            except Exception:
                return []

        users_df["parsed"] = users_df["users"].apply(parse_list)
        mapping = {}
        for comp, grp in users_df.groupby("company"):
            ids = set()
            for lst in grp["parsed"]:
                ids.update(lst)
            for uid in ids:
                mapping[uid] = comp
        cancels["company"] = cancels["userid"].map(mapping)

    if not cancels.empty:
        created_col = "date" if "date" in cancels.columns else "createdat"
        cancels[created_col] = pd.to_datetime(cancels[created_col], errors="coerce")
        cancels["canceldate"] = pd.to_datetime(cancels["canceldate"], errors="coerce")
        cancels["wait_min"] = (cancels["canceldate"] - cancels[created_col]).dt.total_seconds() / 60.0

    # Merge data
    df = (
        orders.merge(
            clients[["userid", "company", "companymanager", "join_date", "mobile"]],
            left_on=orders["userid"].astype(str),
            right_on="userid",
            how="left"
        )
        .dropna(subset=["company"])
    )

    # Parse date filters
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = default_start, today

    df_period = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
    if not include_weekends:
        df_period = df_period[pd.to_datetime(df_period["date"]).dt.weekday < 5]

    # Filter cancels by date and weekends
    cancels_period = pd.DataFrame()
    created_col = "date" if "date" in cancels.columns else "createdat"
    if not cancels.empty:
        cancels_period = cancels[(cancels[created_col].dt.date >= start_date) & (cancels[created_col].dt.date <= end_date)]
        if not include_weekends:
            cancels_period = cancels_period[cancels_period[created_col].dt.weekday < 5]
        
        cancels_period["company"] = cancels_period["company"].fillna("not find company")
        cancels_period = cancels_period.assign(cancel_date=cancels_period[created_col].dt.date)
        
        waits = cancels_period.groupby(["company", "userid", "cancel_date"], as_index=False)["wait_min"].sum()
        first_rows = cancels_period.sort_values(created_col).drop_duplicates(subset=["company", "userid", "cancel_date"], keep="first")
        cancels_period = first_rows.drop(columns=["wait_min"]).merge(waits, on=["company", "userid", "cancel_date"], how="left")

    # Main metrics calculation
    metrics = (
        df_period.groupby("company", as_index=False)
        .agg(
            userid=("userid", "first"),
            join_date=("join_date", "min"),
            manager=("companymanager", "first"),
            sum_orders=("orders", "sum"),
            days_active=("date", "nunique"),
        )
    )
    metrics["avg_orders"] = (metrics["sum_orders"] / metrics["days_active"]).round(2)
    metrics["join_date"] = pd.to_datetime(metrics["join_date"])

    # Filter by avg and join date
    cutoff = today - timedelta(days=int(last_days))
    mask = (metrics["avg_orders"] >= min_avg) | (metrics["join_date"].dt.date >= cutoff)
    selected = metrics.loc[mask, "company"].tolist() or metrics["company"].tolist()

    # Pivot table with daily order sums
    daily_sum = (
        df_period[df_period["company"].isin(selected)]
        .groupby(["company", "date"], observed=True)["orders"]
        .sum()
        .reset_index()
    )
    pivot = daily_sum.pivot(index="company", columns="date", values="orders").fillna(0)
    pivot.columns = [d.strftime("%d.%m.%Y") for d in pivot.columns]

    # Last day's orders
    if not daily_sum.empty:
        last_day = daily_sum["date"].max()
        last_orders = daily_sum[daily_sum["date"] == last_day].set_index("company")["orders"]
    else:
        last_day = end_date
        last_orders = pd.Series(dtype=int)
    metrics["last orders"] = metrics["company"].map(last_orders).fillna(0).astype(int)

    # Final result table assembly
    result = (
        metrics.set_index("company")
        .loc[selected]
        .join(pivot)
        .reset_index()
        .rename(columns={
            "join_date": "join date",
            "sum_orders": "sum",
            "avg_orders": "daily average"
        })
    )
    result.insert(0, "userid", result.pop("userid"))

    # --- Display Area ---
    st.markdown("#### Companies and Daily Orders")
    
    # Display AgGrid or default DataFrame
    try:
        from st_aggrid import AgGrid, GridOptionsBuilder
        gb = GridOptionsBuilder.from_dataframe(result)
        gb.configure_default_column(resizable=True, sortable=True, filter=True, min_column_width=80)
        gb.configure_column("userid", pinned="left", header_name="User ID", width=120)
        gb.configure_column("company", pinned="left", width=100)
        gb.configure_column("join date", pinned="left", type=["dateColumnFilter", "customDateTimeFormat"], custom_format_string="dd.MM.yyyy")
        gb.configure_column("manager", header_name="Manager")
        grid_opts = gb.build()
        AgGrid(result, gridOptions=grid_opts, height=400, enable_enterprise_modules=True)
    except ImportError:
        st.dataframe(result, use_container_width=True, height=400)

    # Download buttons
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            'Download Pivot as CSV',
            result.to_csv(index=False).encode(),
            'companies_daily_orders.csv',
            'text/csv'
        )
    with dl_col2:
        if download_excel_check:
            buf = io.BytesIO()
            result.to_excel(buf, index=False, sheet_name="Orders")
            buf.seek(0)
            st.download_button(
                "Download Pivot as Excel", buf,
                "orders.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # --- Aggregated Statistics ---
    st.markdown('---')
    st.markdown('#### Aggregated Statistics')

    # ... (rest of the script for aggregated stats and charts remains the same)
    # This section is quite long and has its own filters, so it's kept as is.
    
    cancels_daily = pd.DataFrame()
    if not cancels_period.empty:
        st.markdown('**Pure Cancel Filters**')
        cancel_min_wait = st.number_input('Minimum wait (minutes)', min_value=0, value=1)
        tariff_opts = sorted(cancels_period.get('tariff', pd.Series(dtype=str)).dropna().astype(str).unique())
        selected_tariffs_cancel = st.multiselect('Filter tariffs', tariff_opts, default=tariff_opts)
        if selected_tariffs_cancel and 'tariff' in cancels_period.columns:
            cancels_period = cancels_period[cancels_period['tariff'].astype(str).isin(selected_tariffs_cancel)]
        cancels_period = cancels_period[cancels_period['wait_min'] >= cancel_min_wait]
        cancels_daily = (
            cancels_period
            .assign(date=cancels_period[created_col].dt.date)
            .groupby(['company','date'], observed=True)['userid']
            .nunique()
            .reset_index(name='cancels')
        )

    tabs = st.tabs(["Daily", "Weekly", "Monthly"])
    
    def stats_tab(df_orders, df_cancels, period_col, title_col):
        orders_stats = df_orders.groupby(period_col, as_index=False)["orders"].sum()
        cancels_stats = (
            df_cancels.groupby(period_col, as_index=False)["cancels"].sum()
            if not df_cancels.empty else pd.DataFrame(columns=[period_col, "cancels"])
        )
        stats = pd.merge(orders_stats, cancels_stats, on=period_col, how="outer").fillna(0)
        stats = stats.rename(columns={period_col: title_col})

        plot_data = stats.melt(id_vars=title_col, value_vars=["orders", "cancels"], var_name="type", value_name="count")
        chart = (
            alt.Chart(plot_data)
            .mark_line(point=True)
            .encode(
                x=alt.X(f"{title_col}:T", title=title_col.title()),
                y=alt.Y("count:Q", title="Count"),
                color=alt.Color("type:N", title="Metric"),
                tooltip=[alt.Tooltip(f"{title_col}:T"), alt.Tooltip("count:Q"), alt.Tooltip("type:N")]
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)
        st.download_button(f'Download {title_col} Stats', stats.to_csv(index=False).encode(), f'{title_col}_stats.csv', 'text/csv', key=f'dl_{title_col}')
        st.dataframe(stats, use_container_width=True)

    with tabs[0]:
        stats_tab(daily_sum, cancels_daily, 'date', 'date')
    with tabs[1]:
        week_df = daily_sum.copy()
        week_df['week_start'] = pd.to_datetime(week_df['date']).dt.to_period('W').apply(lambda r: r.start_time.date())
        canc_week = cancels_daily.copy()
        if not canc_week.empty:
            canc_week['week_start'] = pd.to_datetime(canc_week['date'], errors='coerce').dt.to_period('W').apply(lambda r: r.start_time.date())
        stats_tab(week_df, canc_week, 'week_start', 'week start')
    with tabs[2]:
        month_df = daily_sum.copy()
        month_df['month_start'] = pd.to_datetime(month_df['date']).dt.to_period('M').apply(lambda r: r.start_time.date())
        canc_month = cancels_daily.copy()
        if not canc_month.empty:
            canc_month['month_start'] = pd.to_datetime(canc_month['date'], errors='coerce').dt.to_period('M').apply(lambda r: r.start_time.date())
        stats_tab(month_df, canc_month, 'month_start', 'month start')


    # считаем отмены именно за last_day по company
    last_cancels = (
        cancels_period[cancels_period["cancel_date"] == last_day]
        .groupby("company")["userid"]
        .count()
    )

    last_df = (
        metrics.set_index("company")[["userid", "last orders"]]
        .rename(columns={"last orders": "orders"})
        .assign(
            cancels=lambda d: d.index.to_series()
                            .map(last_cancels)
                            .fillna(0)
                            .astype(int)
        )
        .reset_index()
    )

    # 2) Таблица суммарных заказов и отмен за период
    total_cancels = (
        cancels_period
        .assign(date=cancels_period["canceldate"].dt.date)
        .groupby("company")["userid"]
        .count()
    )

    totals_df = (
        metrics.set_index("company")[["userid", "sum_orders"]]
        .rename(columns={"sum_orders": "total_orders"})
        .assign(total_cancels=total_cancels)
        .fillna({"total_cancels": 0})
        .reset_index()
    )



    st.markdown("---")
    st.markdown("#### Сводка по последнему дню и за всё время")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**Данные за последний день ({last_day.strftime('%d.%m.%Y')})**")
        st.dataframe(last_df, use_container_width=True)
        st.download_button(
            "Скачать Last Day CSV",
            last_df.to_csv(index=False).encode(),
            f"last_day_{last_day}.csv",
            "text/csv"
        )

    with col2:
        st.markdown("**Итого за выбранный период**")
        st.dataframe(totals_df, use_container_width=True)
        st.download_button(
            "Скачать Totals CSV",
            totals_df.to_csv(index=False).encode(),
            "totals_period.csv",
            "text/csv"
        )
    st.write(f"Last day orders: {metrics['last orders'].sum()}")
    # st.write(f"Last day cancels: {last_cancels.count()}")
    
    # Bottom trend chart and table
    st.markdown('---')
    st.markdown('#### Orders Trend by Company')
    selected_companies = st.multiselect(
        'Select companies for trend', options=metrics['company'].tolist(), default=[]
    )
    if selected_companies:
        # Aggregate and fill missing dates
        trend = (
            df_period[df_period['company'].isin(selected_companies)]
            .groupby(['company', 'date'], as_index=False)['orders']
            .sum()
        )

        # создаём полный ряд дат с учётом include_weekends
        if include_weekends:
            all_dates = pd.date_range(start_date, end_date).date
        else:
            # бизнес-дни (понедельник–пятница)
            all_dates = pd.bdate_range(start_date, end_date).date

        idx = pd.MultiIndex.from_product(
            [selected_companies, all_dates],
            names=['company', 'date']
        )
        trend_full = (
            trend.set_index(['company', 'date'])
                .reindex(idx, fill_value=0)
                .reset_index()
        )

        cancel_trend = pd.DataFrame()
        if not cancels_period.empty:
            cancel_trend = (
                cancels_period[cancels_period['company'].isin(selected_companies)]
                .assign(date=cancels_period[created_col].dt.date)
                .groupby(['company', 'date'], as_index=False)['userid']
                .nunique()
            )
            cancel_trend = (
                cancel_trend.set_index(['company','date'])
                .reindex(idx, fill_value=0)
                .reset_index()
                .rename(columns={'userid':'cancels'})
            )
        trend_full = trend_full.merge(cancel_trend, on=['company','date'], how='left').fillna({'cancels':0})

        # Chart
        melt = trend_full.melt(id_vars=['company','date'], value_vars=['orders','cancels'], var_name='type', value_name='count')
        chart_trend = (
            alt.Chart(melt)
            .mark_line(point=True)
            .encode(
                x=alt.X('date:T', title='Date'),
                y=alt.Y('count:Q', title='Count'),
                color=alt.Color('company:N'),
                strokeDash='type:N',
                tooltip=[alt.Tooltip('date:T'), alt.Tooltip('company:N'), alt.Tooltip('count:Q'), alt.Tooltip('type:N')]
            )
            .properties(height=300)
        )
        st.altair_chart(chart_trend, use_container_width=True)

        # Table и download…
        st.dataframe(trend_full, use_container_width=True)
        st.download_button(
            'Download Trend Data',
            trend_full.to_csv(index=False).encode(),
            'trend_data.csv',
            'text/csv'
        )

        # ------ новый блок: метрика по дням недели ------
        # 1) отфильтруем диапазон по датам, но без учёта include_weekends
        df_range = df[
            (df["date"] >= start_date) &
            (df["date"] <= end_date) &
            (df["company"].isin(selected_companies))
        ].copy()

        # 2) вычисляем имя дня недели
        # df_range['weekday'] = pd.to_datetime(df_range['date']).dt.day_name(locale='en_US')
        weekday_map = {
            0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday',
            4: 'Friday', 5: 'Saturday', 6: 'Sunday'
        }
        df_range['weekday'] = pd.to_datetime(df_range['date']).dt.weekday.map(weekday_map)

        # 3) суммируем заказы по (компания, день недели)
        weekday_stats = (
            df_range
            .groupby(['company', 'weekday'], as_index=False)['orders']
            .sum()
        )

        # 4) приводим к "красивому" порядку столбцов
        order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
        weekday_pivot = (
            weekday_stats
            .pivot(index='company', columns='weekday', values='orders')
            .reindex(columns=order, fill_value=0)
            .reset_index()
        )

        trend = (
            df_period[df_period['company'].isin(selected_companies)]
            .groupby(['company', 'date'], as_index=False)['orders']
            .sum()
        )

        # 5) выводим таблицу
        st.dataframe(weekday_pivot, use_container_width=True, height=300)
        # -----------------------------------------------

        # … здесь ваш существующий блок с трендом …
        # Aggregate and fill missing dates
        trend = (
            df_period[df_period['company'].isin(selected_companies)]
            .groupby(['company', 'date'], as_index=False)['orders']
            .sum()
        )
        # …
    else:
        st.info('Select at least one company to view trend.')