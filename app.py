import streamlit as st
from auth import login
from modules import data_import, gg, tips_analysis, corp_analysis, advanced

st.set_page_config(layout='wide')

# Проверка аутентификации
if not login():
    st.stop()  # Останавливаем выполнение, если не залогинен

# Инициализация данных (только после логина)
if "data" not in st.session_state:
    st.session_state.data = None

# Сайдбар и основной контент (отображаются только после логина)
st.sidebar.title("Navigation")

# data_import.upload_file()
page = st.sidebar.radio("Select a page", ( "Data Import", "gg", "ggTips", "ggBusiness", "Advanced"))
# Чекбоксы для выбора страницы

if page == "Data Import":
    data_import.show()
elif page == "ggTips":
    tips_analysis.show()
elif page == "ggBusiness":
    corp_analysis.show()
elif page == "gg":
    gg.show()
elif page == "Advanced":
    advanced.show()