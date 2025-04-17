# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\modules\data_import.py
import streamlit as st
from data_loader import load_data_from_file
import os
import pandas as pd

# Абсолютный путь к директории для хранения файлов
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploaded_files")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def save_uploaded_file(uploaded_file):
    file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

def load_existing_files():
    return [os.path.join(UPLOAD_DIR, file) for file in os.listdir(UPLOAD_DIR) if file.endswith((".xlsx", ".csv"))]

def delete_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)
        st.success(f"File {os.path.basename(file_path)} deleted successfully.")
    else:
        st.warning(f"File {os.path.basename(file_path)} not found.")

def upload_file():
    # Если в session_state нет списка загруженных файлов, пытаемся загрузить их из папки
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = load_existing_files()
    
    # Если файлов нет, сообщаем пользователю, что нужно их импортировать
    if not st.session_state.uploaded_files:
        st.warning("No files found in uploads folder. Please upload a file.")
    else:
        # Если файлы есть, но данные (clever_data) не загружены или пусты, пробуем загрузить
        if "clever_data" not in st.session_state:
            st.session_state.clever_data = {}
        for file_path in st.session_state.uploaded_files:
            # Если данных по файлу нет или данные пусты, загружаем заново
            if file_path not in st.session_state.clever_data:
                st.session_state.clever_data[file_path] = load_data_from_file(file_path)
            else:
                file_data = st.session_state.clever_data[file_path]
                tips_empty = all(df.empty for df in file_data.get('ggtips', {}).values()) if isinstance(file_data.get('ggtips', {}), dict) else file_data.get('ggtips', pd.DataFrame()).empty
                # Аналогично можно проверить для других ключей при необходимости
                if tips_empty:
                    st.session_state.clever_data[file_path] = load_data_from_file(file_path)
    
    # Затем отображаем file uploader для новых файлов
    uploaded_file = st.file_uploader("Upload Excel or CSV file", type=["xlsx", "csv"])
    if uploaded_file:
        file_path = save_uploaded_file(uploaded_file)
        st.session_state.uploaded_files.append(file_path)
        st.session_state.clever_data[file_path] = load_data_from_file(file_path)
        st.success(f"File {uploaded_file.name} imported successfully.")

def show_file_navigator():
    if not st.session_state.uploaded_files:
        st.warning("No files uploaded yet.")
        return

    selected_file = st.selectbox(
        "Select a file to view its raw data",
        options=st.session_state.uploaded_files,
        format_func=os.path.basename
    )

    if selected_file:
        data_dict = st.session_state.clever_data.get(selected_file, {})

        if data_dict:
            # Первый выбор: ключ верхнего уровня, например 'ggtips', 'ggtipsCompanies', 'ggtipsPartners'
            main_key = st.selectbox("Select main key", options=list(data_dict.keys()))
            sub_data = data_dict.get(main_key)

            # Если sub_data - словарь, выбираем конкретный лист внутри него
            if isinstance(sub_data, dict):
                sub_key = st.selectbox("Select sheet", options=list(sub_data.keys()))
                df = sub_data.get(sub_key)
                st.subheader(f"Data from {os.path.basename(selected_file)} [{main_key} / {sub_key}]")
            else:
                df = sub_data
                st.subheader(f"Data from {os.path.basename(selected_file)} [{main_key}]")

            if df is not None:
                st.dataframe(df)
            else:
                st.warning("Selected sheet is empty or data not found.")
        else:
            st.warning("Data not loaded for selected file.")

def show():
    st.title("📁 Data Import and Viewer")

    upload_file()

    if st.session_state.uploaded_files:
        st.divider()
        st.subheader("📂 Uploaded Files")
        for idx, file_path in enumerate(st.session_state.uploaded_files):
            col1, col2 = st.columns([0.8, 0.2])
            col1.write(os.path.basename(file_path))

            unique_key = f"{file_path}_{idx}"
            if col2.button("Delete", key=unique_key):
                delete_file(file_path)
                st.session_state.uploaded_files.remove(file_path)
                st.session_state.clever_data.pop(file_path, None)
                st.rerun()

    st.divider()
    show_file_navigator()

if __name__ == "__main__":
    show()
