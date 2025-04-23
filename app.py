# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\app.py
import streamlit as st
from auth import login
from modules import data_import, corp_analysis, advanced
from modules.ggTipsModule import ggTips
from modules.ggModule import gg
from modules.ggTipsModule import ggTips_navigation

st.set_page_config(layout='wide')

# Проверка аутентификации
if not login():
    st.stop()  # Останавливаем выполнение, если не залогинен

# Инициализация данных (только после логина)
if "data" not in st.session_state:
    st.session_state.data = None

# Сайдбар и основной контент (отображаются только после логина)

with st.sidebar:
    page = st.radio("Select a page", ( "Data Import", "gg", "ggTips", "ggBusiness", "Developer mode"))
    # Фильтры ggTips будем показывать, только если выбрана соответствующая страница

    if page == "ggTips":
         
        if "data" in st.session_state and st.session_state.clever_data:
            filtered_tips = ggTips_navigation.show_ggtips_sidebar_filters(st.session_state.clever_data)
        else:
            filtered_tips = None
            
if page == "Data Import":
    data_import.show()
elif page == "ggTips":
    ggTips.show(filtered_tips)
elif page == "ggBusiness":
    corp_analysis.show()
elif page == "gg":
    gg.show()
elif page == "Developer mode":
    advanced.show()