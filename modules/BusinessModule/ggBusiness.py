# modules/BusinessModule/ggBusiness.py

import streamlit as st
from modules.data_import import upload_file
from modules.BusinessModule.ggBusinessTabs import ordersTab, activationsTab
from modules.BusinessModule.ggBusinessData import get_combined_business_data

def show(clever_data):
    st.title("ggBusiness Analysis")

    # Если данных нет — просим загрузить
    if not clever_data:
        st.warning("No data available. Please import data first.")
        upload_file()
        st.stop()

    data = get_combined_business_data(clever_data)

    tab1, tab2 = st.tabs(["Orders", "Statistics"])

    with tab1:
        ordersTab.show(data)

    with tab2:
        st.write(data)
        # if data["statistic"].empty:
        #     st.info("No statistics sheet found in any file.")
        # else:
        #     st.dataframe(data["statistic"], use_container_width=True)
