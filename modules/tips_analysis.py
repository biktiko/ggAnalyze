# tips_analyze.py
import streamlit as st
import pandas as pd
import numpy as np
from ggTipsTabs.AllTipsTab import show_all_tips_tab
from data_loader import merge_sheets

def show():
    st.title("Tips Analysis")

    
    if "clever_data" not in st.session_state or not st.session_state.clever_data:
        st.warning("No data available. Please import data first.")
        from modules import data_import
        data_import.upload_file()
        return
    else:
        combined_data = []
        for file_data in st.session_state.clever_data.values():
            merged_df = merge_sheets(file_data)
            if not merged_df.empty:
                combined_data.append(merged_df)

        if combined_data:
            st.session_state.data = pd.concat(combined_data, ignore_index=True)
        else:
            st.session_state.data = pd.DataFrame()

        
    # Создаем вкладки
    AllTipsTab, CompaniesTipsTab, CompaniesActivactions, CompanyConnectionsTab, TablesTab, MapTab, UsersTab = st.tabs(
        ['ggTips', 'Top companies', 'Companies activations', 'Company connections', 'Tables', 'Map', 'Users']
    )

    # Отображаем содержимое вкладки AllTips
    with AllTipsTab:
        show_all_tips_tab(st.session_state.data)  # Вызываем функцию с данными

    # Здесь можно добавить содержимое других вкладок
    with CompaniesTipsTab:
        st.write("### Top Companies Tab")
        st.write("To be implemented...")

    with CompaniesActivactions:
        st.write("### Companies Activations Tab")
        st.write("To be implemented...")

    with CompanyConnectionsTab:
        st.write("### Company Connections Tab")
        st.write("To be implemented...")

    with TablesTab:
        st.write("### Tables Tab")
        st.write("To be implemented...")

    with MapTab:
        st.write("### Map Tab")
        st.write("To be implemented...")

    with UsersTab:
        st.write("### Users Tab")
        st.write("To be implemented...")

# Запуск приложения (если это основной файл)
if __name__ == "__main__":
    show()