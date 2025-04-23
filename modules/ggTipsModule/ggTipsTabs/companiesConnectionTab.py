# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\modules\ggTipsModule\ggTipsTabs\companyConnectionsTab.py

import streamlit as st
import pandas as pd
import altair as alt

def show(data: dict | None = None) -> None:
    """
    Вкладка «Company Connections» показывает, как менялось число активных филиалов
    и уникальных компаний во времени, а также их суточные приросты.
    """
    st.subheader("Company connections")

    st.write('! Այս պահին որոշակի շեղումներ կարող են լինել !')

    # 1) Получаем таблицу компаний
    companies = data.get("ggtipsCompanies", pd.DataFrame()).copy()
    if companies.empty:
        st.info("No company data for connections yet.")
        return

    # 2) Преобразуем колонки start и end в datetime
    companies['start'] = pd.to_datetime(companies.get('start'), errors='coerce')
    companies['end']   = pd.to_datetime(companies.get('end'),   errors='coerce')

    # 3) UI: диапазон дат и уровень агрегации
    with st.expander("Config", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "From date",
                value=companies['start'].min().date(),
                key="conn_start_date"
            )
            end_date = st.date_input(
                "To date",
                value=pd.to_datetime("today").date(),
                key="conn_end_date"
            )
        with col2:
            time_interval = st.selectbox(
                "Group by",
                ["Day", "Week", "Month", "Year"],
                index=1,
                key="conn_time_interval"
            )

    # 4) Собираем статистику по каждому дню
    drange = pd.date_range(start=pd.to_datetime(start_date), end=pd.to_datetime(end_date))
    stats = []
    for day in drange:
        active = companies[
            (companies['start'].notna()) &
            ((companies['end'].isna()) | (companies['end'] >= day)) &
            (companies['start'] <= day)
        ]
        stats.append({
            'Date': day,
            'Active Branches': active.shape[0],
            'Active Companies': active['helpercompanyname'].nunique()
        })
    df = pd.DataFrame(stats)

    # 5) Рассчитываем суточные дельты
    df['Branches Change']  = df['Active Branches'].diff().fillna(0)
    df['Companies Change'] = df['Active Companies'].diff().fillna(0)

    # 6) Приводим Date к нужному уровню агрегации
    if time_interval == 'Day':
        df['Period'] = df['Date'].dt.normalize()
    elif time_interval == 'Week':
        df['Period'] = df['Date'] - pd.to_timedelta(df['Date'].dt.weekday, unit='D')
    elif time_interval == 'Month':
        df['Period'] = df['Date'].dt.to_period('M').apply(lambda r: r.start_time)
    else:  # Year
        df['Period'] = pd.to_datetime(df['Date'].dt.year.astype(str) + '-01-01')

    # 7) Группируем для линейного тренда
    grouped = (
        df
        .groupby('Period', observed=True)
        .agg({
            'Active Branches': 'max',
            'Active Companies': 'max',
            'Branches Change': 'sum',
            'Companies Change': 'sum'
        })
        .reset_index()
    )

    # 8) Линейный график тренда
    line_branches = alt.Chart(grouped).mark_line(color='green').encode(
        x=alt.X('Period:T', title='Date'),
        y=alt.Y('Active Branches:Q', title='Active Branches / Companies'),
        tooltip=[alt.Tooltip('Period:T', title='Date'),
                 alt.Tooltip('Active Branches:Q', title='Branches')]
    )
    line_companies = alt.Chart(grouped).mark_line(color='blue').encode(
        x='Period:T',
        y=alt.Y('Active Companies:Q'),
        tooltip=[alt.Tooltip('Period:T', title='Date'),
                 alt.Tooltip('Active Companies:Q', title='Companies')]
    )

    st.altair_chart(
        alt.layer(line_branches, line_companies)
           .configure_axis(labelColor='white', titleColor='white'),
        use_container_width=True
    )

    # 9) Бар-чарт ежедневных изменений (с отрицательными значениями)
    bars_br = alt.Chart(df).mark_bar(color='green').encode(
        x=alt.X('Date:T', title='Date'),
        y=alt.Y('Branches Change:Q', title='Daily Change', stack=None),
        tooltip=[alt.Tooltip('Date:T', title='Date'),
                 alt.Tooltip('Branches Change:Q', title='Branches Δ')]
    )
    bars_co = alt.Chart(df).mark_bar(color='blue').encode(
        x='Date:T',
        y=alt.Y('Companies Change:Q', title='Daily Change', stack=None),
        tooltip=[alt.Tooltip('Date:T', title='Date'),
                 alt.Tooltip('Companies Change:Q', title='Companies Δ')]
    )

    st.altair_chart(
        alt.layer(bars_br, bars_co)
           .configure_axis(labelColor='white', titleColor='white'),
        use_container_width=True
    )

    # 10) Детальная таблица итогов
    with st.expander('Table', expanded=False):
        st.dataframe(grouped, use_container_width=True)
