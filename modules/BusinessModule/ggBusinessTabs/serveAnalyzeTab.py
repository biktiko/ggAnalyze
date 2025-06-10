import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import io

def show(data: dict, filters: dict) -> None:
    st.title("ggBusiness Analyze Tab")