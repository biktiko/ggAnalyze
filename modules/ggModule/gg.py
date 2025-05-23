# tips_analyze.py
import streamlit as st
import pandas as pd
import numpy as np
from modules.ggModule.ggPages.Comparison import comparison_show

def show():
    st.title("ggAnalyze")
        
    # Создаем вкладки
    Comparison, other = st.tabs(
        ['Comparison', 'other']
    )

    # Отображаем содержимое вкладки AllTips
    with Comparison:
        comparison_show()

    with other:
        st.write('other')