import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import io
from modules.BusinessModule.businessFilters import get_common_filters
# from BusinessModule.businessFilters import get_common_filters

def show(data: dict, filters: dict) -> None:
    """
    Tab "Orders" — daily analytics of company orders.
    Принимает:
      - data: {"orders": DataFrame, "clients": DataFrame}
      - filters: результат get_common_filters()
    """
    # распаковываем фильтры
    min_avg          = filters["min_avg"]
    last_days        = filters["last_days"]
    date_range       = filters["date_range"]
    download         = filters["download"]
    include_weekends = filters["include_weekends"]
    today            = filters["today"]
    default_start    = filters["default_start"]

    st.subheader("Daily Orders per Company")

    orders  = data.get("orders", pd.DataFrame()).copy()
    clients = data.get("clients", pd.DataFrame()).copy()
    if orders.empty or clients.empty:
        st.info("Not enough data: please upload both 'orders' and 'clients'.")
        return

    # подготовка дат
    orders["date"]      = pd.to_datetime(orders["date"], errors="coerce").dt.date
    clients["userid"]   = clients["userid"].astype(str)
    clients["join_date"]= pd.to_datetime(clients.get("date"), errors="coerce").dt.date

    # объединяем данные
    df = (
        orders.merge(
            clients[["userid","company","companymanager","join_date"]],
            left_on=orders["userid"].astype(str),
            right_on="userid", how="left"
        )
        .dropna(subset=["company"])
    )

    # разбираем дату
    if isinstance(date_range, (list, tuple)) and len(date_range)==2:
        start_date, end_date = date_range
    else:
        start_date, end_date = default_start, today

    # фильтруем по дате
    df_period = df[(df["date"]>=start_date)&(df["date"]<=end_date)]
    if not include_weekends:
        df_period = df_period[pd.to_datetime(df_period["date"]).dt.weekday<5]

    # основные метрики
    metrics = (
        df_period.groupby("company", as_index=False)
        .agg(
            join_date   = ("join_date","min"),
            manager     = ("companymanager","first"),
            sum_orders  = ("orders","sum"),
            days_active = ("date","nunique")
        )
    )
    metrics["avg_orders"]  = (metrics["sum_orders"]/metrics["days_active"]).round(2)
    metrics["join_date"]   = pd.to_datetime(metrics["join_date"])

    # фильтр по avg и дате подключения
    cutoff = today - timedelta(days=int(last_days))
    mask   = (metrics["avg_orders"]>=min_avg)|(metrics["join_date"].dt.date>=cutoff)
    selected = metrics.loc[mask, "company"].tolist() or metrics["company"].tolist()

    # строим pivot-таблицу
    daily_sum = (
        df_period[df_period["company"].isin(selected)]
        .groupby(["company","date"], observed=True)["orders"]
        .sum().reset_index()
    )
    pivot = daily_sum.pivot(index="company",columns="date",values="orders").fillna(0)
    pivot.columns = [d.strftime("%d.%m.%Y") for d in pivot.columns]

    # последние заказы
    if not daily_sum.empty:
        last_day    = daily_sum["date"].max()
        last_orders = daily_sum[daily_sum["date"]==last_day].set_index("company")["orders"]
    else:
        last_orders = pd.Series(dtype=int)
    metrics["last orders"] = metrics["company"].map(last_orders).fillna(0).astype(int)

    # финальная таблица
    result = (
        metrics.set_index("company").loc[selected]
        .join(pivot)
        .reset_index()
        .rename(columns={
            "join_date":"join date",
            "sum_orders":"sum",
            "avg_orders":"daily average"
        })
    )

    # скачивание Excel
    if download:
        buf = io.BytesIO()
        result.to_excel(buf, index=False, sheet_name="Orders")
        buf.seek(0)
        st.sidebar.download_button(
            "Download Excel", buf,
            "orders.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # отображение с AgGrid (если доступен)
    st.markdown("#### Companies and Daily Orders")
    try:
        from st_aggrid import AgGrid, GridOptionsBuilder
        gb = GridOptionsBuilder.from_dataframe(result)
        gb.configure_default_column(resizable=True, sortable=True, filter=True, min_column_width=80)
        gb.configure_column("company", pinned="left", width=150)
        gb.configure_column(
            "join date",
            pinned="left",
            type=["dateColumnFilter","customDateTimeFormat"],
            custom_format_string="dd.MM.yyyy",
            header_name="Join Date"
        )
        gb.configure_column("manager", header_name="Менеджер")
        grid_opts = gb.build()
        AgGrid(result, gridOptions=grid_opts, height=400, enable_enterprise_modules=True)
    except ImportError:
        st.dataframe(result, use_container_width=True, height=400)

    # Aggregated stats in tabs
    st.markdown('---')
    st.markdown('#### Aggregated Statistics')
    tabs = st.tabs(["По дням", "По неделям", "По месяцам"])

    # Function to create stats tab
    def stats_tab(df_input, period_col, title_col):
        stats = df_input.groupby(period_col, as_index=False)['orders'].sum().rename(columns={period_col: title_col})
        # Chart with impute to show zeros
        chart = (alt.Chart(stats)
                 .transform_impute(
                     impute='orders',
                     key=title_col,
                     groupby=['company'],
                     value=0
                 )
                 .mark_line(point=True)
                 .encode(
                     x=alt.X(f'{title_col}:T', title=title_col.title()),
                     y=alt.Y('orders:Q', title='Orders'),
                     color=alt.Color('company:N', title='Company'),
                     tooltip=[alt.Tooltip(f'{title_col}:T'), alt.Tooltip('orders:Q'), alt.Tooltip('company:N')]
                 )
                 .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)
        st.download_button(f'Download {title_col} Stats', stats.to_csv(index=False).encode(), f'{title_col}_stats.csv', 'text/csv')
        st.dataframe(stats, use_container_width=True)

    # Daily
    with tabs[0]:
        st.subheader("Статистика по дням")
        stats_tab(daily_sum, 'date', 'date')

    # Weekly
    with tabs[1]:
        st.subheader("Статистика по неделям")
        week_df = daily_sum.copy()
        week_df['week_start'] = pd.to_datetime(week_df['date']).dt.to_period('W').apply(lambda r: r.start_time.date())
        stats_tab(week_df, 'week_start', 'week start')

    # Monthly
    with tabs[2]:
        st.subheader("Статистика по месяцам")
        month_df = daily_sum.copy()
        month_df['month_start'] = pd.to_datetime(month_df['date']).dt.to_period('M').apply(lambda r: r.start_time.date())
        stats_tab(month_df, 'month_start', 'month start')

    # Bottom trend chart and table
    st.markdown('---')
    st.markdown('#### Orders Trend by Company')
    selected_companies = st.multiselect(
        'Select companies for trend', options=metrics['company'].tolist(), default=[]
    )
    if selected_companies:
        # Aggregate and fill missing dates
        trend = df_period[df_period['company'].isin(selected_companies)].groupby(['company', 'date'], as_index=False)['orders'].sum()
        # create complete frame
        all_dates = pd.date_range(start_date, end_date).date
        idx = pd.MultiIndex.from_product([selected_companies, all_dates], names=['company', 'date'])
        trend_full = trend.set_index(['company', 'date']).reindex(idx, fill_value=0).reset_index()
        # Chart
        chart_trend = (alt.Chart(trend_full)
                       .mark_line(point=True)
                       .encode(
                           x=alt.X('date:T', title='Date'),
                           y=alt.Y('orders:Q', title='Orders'),
                           color=alt.Color('company:N'),
                           tooltip=[alt.Tooltip('date:T'), alt.Tooltip('company:N'), alt.Tooltip('orders:Q')]
                       )
                       .properties(height=300)
        )
        st.altair_chart(chart_trend, use_container_width=True)
        # Table
        st.dataframe(trend_full, use_container_width=True)
        # Download
        st.download_button('Download Trend Data', trend_full.to_csv(index=False).encode(), 'trend_data.csv', 'text/csv')
    else:
        st.info('Select at least one company to view trend.')
