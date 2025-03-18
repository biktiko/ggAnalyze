import streamlit as st
from utils import create_bar_chart

def show():
    st.header("Corporate Analysis")
    tab_charts, tab_tables = st.tabs(["Charts", "Tables"])
    
    with tab_charts:
        st.write("Charts for corporate analysis.")
        if st.session_state.data is not None:
            create_bar_chart(st.session_state.data, "date", "indicator", "Corporate Indicators")
        else:
            st.info("No data available. Please upload a file on the 'Data Import' page.")
    
    with tab_tables:
        st.write("Corporate data table.")
        if st.session_state.data is not None:
            st.dataframe(st.session_state.data)
        else:
            st.info("No data available.")