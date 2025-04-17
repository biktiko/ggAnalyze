import streamlit as st
import altair as alt
import pandas as pd

def show(data=None):
    """Функция для отображения содержимого вкладки AllTips."""
    
    if data is None:
        st.warning("No data to display in All Tips Tab.")
        return

    with st.expander("Stats", expanded=False):
        from modules.ggTipsModule.ggTipsTabs import stats
        stats.show(data)

    # Предполагается, что data['ggtipsGrouped'] содержит столбцы, например:
    # time_group (дата/категория), Amount (сумма), Count (кол-во транзакций)
    groupedTips = data.get('ggtipsGrouped', pd.DataFrame()).copy()

    if groupedTips.empty:
        st.warning("No grouped data to display.")
        return

    # -- Блок настроек графика --
    with st.expander("Chart settings", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            sort_column = st.selectbox("Select column for sorting", ["Time", "Amount", "Count"], key="sort_col_all")
        with col2:
            sort_direction = st.selectbox("Select sort direction", ["Descending", "Ascending"], key="sort_dir_all")
        with col3:
            max_bars = st.number_input("Max columns to display", value=20, min_value=1, step=1, key="max_bars_all")

    # Проверяем, что у нас есть нужные столбцы
    needed = {"time_group", "Amount", "Count"}
    if not needed.issubset(groupedTips.columns):
        st.warning(f"Grouped data must have columns {needed}. Found: {groupedTips.columns.tolist()}")
        return

    # ----- Сортировка и ограничение кол-ва столбцов -----
    x_axis_type = 'T'  # Предположим, что time_group - это реальная дата (datetime64)
                       # Если у Вас при месячной группировке хранятся только числа 1..12,
                       # нужно либо преобразовать их в дату (например, '2025-01-01' и т.д.),
                       # либо относиться к ним как к категории (x_axis_type='O').

    if sort_column == "Time":
        # Предполагаем, что Period - это datetime (или можно попытаться pd.to_datetime)
        groupedTips['time_group'] = pd.to_datetime(groupedTips['time_group'], errors='coerce')
        if sort_direction == "Descending":
            # Сортируем от более поздней даты к ранней, берем первые max_bars,
            # затем переворачиваем обратно, чтобы ось X шла слева направо
            groupedTips = (groupedTips
                           .sort_values(by='time_group', ascending=False)
                           .head(max_bars)
                           .sort_values(by='time_group', ascending=True))
        else:
            # Сортируем по возрастанию, берем первые max_bars
            groupedTips = groupedTips.sort_values(by='time_group', ascending=True).head(max_bars)
    else:
        # Сортируем по Amount или Count
        if sort_direction == "Descending":
            groupedTips = groupedTips.sort_values(by=sort_column, ascending=False).head(max_bars)
        else:
            groupedTips = groupedTips.sort_values(by=sort_column, ascending=True).head(max_bars)
        # Для этих случаев ось X будет категориальной
        x_axis_type = 'O'

    # ----- Построение графика Altair -----
    column_size = 30
    sum_color = 'green'
    count_color = 'blue'

    if x_axis_type == 'T':
        x_axis = alt.X("time_group:T", axis=alt.Axis(format="%b %Y", title="Time"))
    else:
        # Категориальная ось: строка
        groupedTips['time_group'] = groupedTips['time_group'].astype(str)
        x_axis = alt.X("time_group:O", axis=alt.Axis(title="time_group"), sort=None)

    # Бар-чарт для Amount
    sum_layer = alt.Chart(groupedTips).mark_bar(
        size=column_size,
        color=sum_color,
        stroke='white',
        strokeWidth=1
    ).encode(
        x=x_axis,
        y=alt.Y('Amount:Q', axis=alt.Axis(title='Sum of Tips')),
        tooltip=['time_group', 'Amount', 'Count']
    )

    # Линейный график для Count
    count_layer = alt.Chart(groupedTips).mark_line(
        color=count_color,
        strokeWidth=3
    ).encode(
        x=x_axis,
        y=alt.Y('Count:Q', axis=alt.Axis(title='Count of Transactions')),
        tooltip=['time_group', 'Amount', 'Count']
    )

    chart = alt.layer(sum_layer, count_layer).resolve_scale(y='independent').configure_axis(
        labelColor='white',
        titleColor='white'
    )

    st.altair_chart(chart, use_container_width=True)