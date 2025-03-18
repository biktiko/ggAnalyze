# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\ggTipsTabs\AllTipsTab.py
import streamlit as st
import pandas as pd

def show_all_tips_tab(data=None):
    """Функция для отображения содержимого вкладки AllTips."""
    
    st.write("### All Tips Tab")
    if data is not None:
        st.write(data)
    else:
        st.warning("No data to display in All Tips Tab.")