import streamlit as st
import altair as alt
import pandas as pd

def create_line_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str) -> None:
    """Создает линейный график для данных."""
    if x_col in df.columns and y_col in df.columns:
        chart = alt.Chart(df).mark_line().encode(
            x=alt.X(f"{x_col}:T", title="Date"),
            y=alt.Y(f"{y_col}:Q", title=y_col)
        ).properties(title=title)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.warning(f"Data must contain '{x_col}' and '{y_col}' columns.")

def create_bar_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str, color: str = "#00FF00") -> None:
    """Создает столбчатый график для данных."""
    if x_col in df.columns and y_col in df.columns:
        chart = alt.Chart(df).mark_bar(color=color).encode(
            x=alt.X(f"{x_col}:T", title="Date"),
            y=alt.Y(f"{y_col}:Q", title=y_col)
        ).properties(title=title)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.warning(f"Data must contain '{x_col}' and '{y_col}' columns.")