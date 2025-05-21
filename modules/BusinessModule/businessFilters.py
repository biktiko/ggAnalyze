import streamlit as st
from datetime import datetime, timedelta

def get_common_filters():
    """
    Возвращает общие фильтры для боковой панели:
      - min_avg: float
      - last_days: int
      - date_range: tuple(date, date)
      - download: bool
      - include_weekends: bool
      - today: date
      - default_start: date
    """
    st.sidebar.header('Filters')
    min_avg = st.sidebar.number_input('Min. avg orders per day', 0.0, None, 1.0, 0.1)
    last_days = st.sidebar.number_input('Companies joined in last N days', 0, None, 7)
    today = datetime.today().date()
    default_start = today - timedelta(days=30)
    date_range = st.sidebar.date_input('Date range for table', value=(default_start, today))
    download = st.sidebar.checkbox('Download Excel')
    include_weekends = st.sidebar.checkbox('Include weekends', value=True)

    return {
        'min_avg': min_avg,
        'last_days': last_days,
        'date_range': date_range,
        'download': download,
        'include_weekends': include_weekends,
        'today': today,
        'default_start': default_start
    }