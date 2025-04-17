import streamlit as st

def show(data=None):
    """Функция для отображения содержимого вкладки AllTips."""
    
    st.write("### All Tips Tab")
    if data is None:
        st.warning("No data to display in All Tips Tab.")
        return

    # Извлекаем данные, которые ранее были возвращены в виде словаря
    ggTipsDataFiltered = data['ggtips']
    ggTipsDataGrouped = data['ggtipsGrouped']
    ggTipsCompaniesData = data['ggtipsCompanies']
    ggTipsPartnersData = data['ggtipsPartners']
    ggTeammatesData = data['ggTeammates']

    # st.write(ggTipsCompaniesData)

    if not ggTipsDataFiltered.empty:
        with st.expander("Stats", expanded=False):
            from modules.ggTipsModule.ggTipsTabs import stats
            stats.show(data)

    st.write("ggTips Data Filtered")
    st.write(ggTipsDataFiltered)

    st.write("ggTips Group Data Filtered")
    st.write(ggTipsDataGrouped)  
    
    st.write("ggTips Companies Data Filtered")
    st.write(ggTipsCompaniesData)

    st.write("ggTips Partners Filtered")
    st.write(ggTipsPartnersData)

    st.write("ggTips Teammates")
    st.write(ggTeammatesData)