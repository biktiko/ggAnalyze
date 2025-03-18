import streamlit as st

def show():
    st.subheader("Session State")
    st.write(st.session_state)