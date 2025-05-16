import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import io

# Optional: for advanced table features (column freezing)
try:
    from st_aggrid import AgGrid, GridOptionsBuilder
    AGGRID_AVAILABLE = True
except ImportError:
    AGGRID_AVAILABLE = False


def show(data: dict) -> None:
    """
    Tab "Orders" — daily analytics of company orders.
    Expects data = {"orders": DataFrame, "clients": DataFrame}.
    """
    st.subheader("Daily Orders per Company")

    # load data
    orders = data.get("orders", pd.DataFrame()).copy()
    clients = data.get("clients", pd.DataFrame()).copy()
    if orders.empty or clients.empty:
        st.info("Not enough data: please upload both 'orders' and 'clients'.")
        return

    # prepare dates and types
    orders['date'] = pd.to_datetime(orders['date'], errors='coerce').dt.date
    clients['userid'] = clients['userid'].astype(str)
    clients['join_date'] = pd.to_datetime(clients.get('date'), errors='coerce').dt.date

    # merge datasets
    df = orders.merge(
        clients[['userid','company','companymanager','join_date']],
        left_on=orders['userid'].astype(str),
        right_on='userid', how='left'
    ).dropna(subset=['company'])

    # compute metrics per company
    metrics = df.groupby('company', as_index=False).agg(
        join_date=('join_date','min'),
        manager=('companymanager','first'),
        sum_orders=('orders','sum'),
        days_active=('date','nunique')
    )
    metrics['avg_orders'] = (metrics['sum_orders']/metrics['days_active']).round(2)

    # sidebar filters
    st.sidebar.header('Filters')
    min_avg = st.sidebar.number_input('Min. avg orders per day', 0.0, None, 1.0, 0.1)
    last_days = st.sidebar.number_input('Companies joined in last N days', 0, None, 7)
    today = datetime.today().date()
    default_start = today - timedelta(days=30)
    date_range = st.sidebar.date_input('Date range for table', [default_start, today])
    download = st.sidebar.checkbox('Download Excel')

    # select companies for table
    cutoff = today - timedelta(days=int(last_days))
    mask = (metrics['avg_orders'] >= min_avg) | (metrics['join_date'] >= cutoff)
    selected = metrics.loc[mask, 'company'].tolist() or metrics['company'].tolist()

    # pivot table data
    daily_sum = df.groupby(['company','date'], observed=True)['orders'].sum().reset_index()
    pivot = (
        daily_sum[daily_sum['company'].isin(selected)]
        .pivot(index='company', columns='date', values='orders').fillna(0)
    )
    if not pivot.columns.empty:
        last_date = pivot.columns.max()
        last_day_orders = daily_sum[daily_sum['date'] == last_date].set_index('company')['orders']
    else:
        last_day_orders = pd.Series(dtype=int)

    # apply date filter
    start_date, end_date = (date_range if isinstance(date_range, list) and len(date_range) == 2 else (default_start, today))
    pivot = pivot.loc[:, pivot.columns.to_series().between(start_date, end_date)]
    pivot.columns = [d.strftime('%d.%m.%Y') for d in pivot.columns]

    # combine metrics and pivot
    metrics['last orders'] = metrics['company'].map(last_day_orders).fillna(0).astype(int)
    result = (
        metrics.set_index('company').loc[selected]
        .join(pivot).reset_index()
    )
    result['join_date'] = pd.to_datetime(result['join_date']).dt.strftime('%d.%m.%Y')
    result.rename(columns={
        'join_date':'join date',
        'sum_orders':'sum',
        'avg_orders':'daily average',
        'last orders':'last orders'
    }, inplace=True)

    # download Excel
    if download:
        buf = io.BytesIO()
        result.to_excel(buf, index=False, sheet_name='Orders')
        buf.seek(0)
        st.sidebar.download_button('Download Excel', buf, 'orders.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # display table
    st.markdown('#### Companies and Daily Orders')
    if AGGRID_AVAILABLE:
        gb = GridOptionsBuilder.from_dataframe(result)
        freeze_cols = ['company','join date','manager','sum','daily average','last orders']
        for c in freeze_cols:
            gb.configure_column(c, pinned='left')
        gb.configure_column('company', width=50)
        gb.configure_default_column(resizable=True, sortable=True, filter=True, min_column_width=80)
        grid_opts = gb.build()
        AgGrid(result, gridOptions=grid_opts, fit_columns_on_grid_load=False, height=400)
    else:
        st.dataframe(result, use_container_width=True, height=400)

    # bottom chart: daily orders trend
    st.markdown('---')
    st.markdown('#### Daily Orders Trend')
    chart_companies = st.multiselect('Select companies for chart', options=metrics['company'].tolist(), default=[])
    if chart_companies:
        chart_df = daily_sum[daily_sum['company'].isin(chart_companies)]
        chart_df = chart_df[(chart_df['date'] >= start_date) & (chart_df['date'] <= end_date)]
        chart = (alt.Chart(chart_df)
                 .mark_line(point=True)
                 .encode(
                     x=alt.X('date:T', title='Date'),
                     y=alt.Y('orders:Q', title='Orders', axis=alt.Axis(format='d', tickMinStep=1)),
                     color=alt.Color('company:N', title='Company'),
                     tooltip=[alt.Tooltip('date:T', title='Date'), alt.Tooltip('company:N', title='Company'), alt.Tooltip('orders:Q', title='Orders')]
                 )
                 .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info('Select at least one company to display the trend chart.')
