# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\app.py
import streamlit as st
from auth import login
st.set_page_config(layout='wide')

from modules import data_import, advanced
from modules.ggTipsModule import ggTips
from modules.BusinessModule import ggBusiness
from modules.ggModule import gg
from modules.ggTipsModule import ggTips_navigation
from modules.CarseatModule import carseat


# Проверка аутентификации
if not login():
    st.stop()  # Останавливаем выполнение, если не залогинен

# Инициализация данных (только после логина)
if "data" not in st.session_state:
    st.session_state.data = None

# Сайдбар и основной контент (отображаются только после логина)

with st.sidebar:
    page = st.radio("Select a page", ( "Data Import", "gg", "ggTips", "ggBusiness", "Carseat", "Developer mode"))
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
    elif page == "Carseat":
        if "data" in st.session_state and st.session_state.clever_data:
            CarseatData = st.session_state.clever_data
        else:
            CarseatData = None
            
if page == "Data Import":
    data_import.show()
elif page == "gg":
    gg.show()
elif page == "ggTips":
    ggTips.show(filteredTips)
elif page == "ggBusiness":
    ggBusiness.show(ggBusinessData)
elif page == "Carseat":
    carseat.show(CarseatData) 
elif page == "Developer mode":
    advanced.show()
