# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\modules\ggTipsModule\ggTips.py
import streamlit as st
from modules.data_import import upload_file
from modules.BusinessModule.ggBusinessTabs import ordersTab, activationsTab
from modules.BusinessModule.ggBusinessData import get_combined_business_data

def show(data):
    st.title("ggBusiness Analysis")
    # Если данные не переданы, вызываем интерфейс загрузки данных
    if data is None:
        st.warning("No data available. Please import data first.")
        upload_file()  # Показываем загрузчик файлов
        st.rerun() 

    data = get_combined_business_data(data)
            
    OrdersTab, ActivationsTab = st.tabs(
        ['Orders', 'Activations']
    )

    with OrdersTab:
        ordersTab.show(data)

    with ActivationsTab:
        st.write("Activations data will be shown here.")

