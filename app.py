# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\app.py
import streamlit as st
st.set_page_config(layout='wide')

from auth import login
from modules import data_import, advanced
from modules.ggTipsModule import ggTips
from modules.BusinessModule import ggBusiness
from modules.ggModule import gg
from modules.ggTipsModule import ggTips_navigation


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
            filteredTips = ggTips_navigation.show_ggtips_sidebar_filters(st.session_state.clever_data)
        else:
            filteredTips = None
    elif page=='ggBusiness':
        if "data" in st.session_state and st.session_state.clever_data:
            ggBusinessData =st.session_state.clever_data
        else:
            ggBusinessData = None
            
if page == "Data Import":
    data_import.show()
elif page == "ggTips":
    ggTips.show(filteredTips)
elif page == "ggBusiness":
    ggBusiness.show(ggBusinessData)
elif page == "gg":
    gg.show()
elif page == "Developer mode":
    advanced.show()
