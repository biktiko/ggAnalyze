# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\modules\ggTipsModule\ggTips.py
import streamlit as st
from modules.data_import import upload_file  # Импорт функции загрузки данных
from modules.ggTipsModule.ggTipsTabs import CompaniesTab, allTipsTab, tablesTab, companyActivactionTab, mapsTab, companiesConnectionTab, usersTab

def show(data):
    st.title("Tips Analysis")
    # Если данные не переданы, вызываем интерфейс загрузки данных
    if data is None:
        st.warning("No data available. Please import data first.")
        upload_file()  # Показываем загрузчик файлов
        st.rerun() 
            
    AllTipsTab, CompaniesTipsTab, CompaniesActivactions, CompanyConnectionsTab, MapTab, UsersTab, TablesTab = st.tabs(
        ['ggTips', 'Top companies', 'Companies activations', 'Company connections', 'Map', 'Users', 'Tables']
    )

    with AllTipsTab:
        allTipsTab.show(data)

    with CompaniesTipsTab:
        CompaniesTab.show(data)

    with CompaniesActivactions:
        companyActivactionTab.show(data)

    with CompanyConnectionsTab:
       companiesConnectionTab.show(data)

    with MapTab:
        mapsTab.show(data)

    with UsersTab:
        usersTab.show(data)

    with TablesTab:
        tablesTab.show(data)
