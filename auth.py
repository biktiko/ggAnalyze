import streamlit as st

def login():
    # Инициализация состояния аутентификации
    if "authenticated" not in st.session_state:
        # Проверяем параметр URL
        if "auth" in st.query_params and st.query_params["auth"] == "true":
            st.session_state.authenticated = True
        else:
            st.session_state.authenticated = False

    # Если пользователь уже аутентифицирован, возвращаем True
    if st.session_state.authenticated:
        return True

    # Форма логина
    with st.form("login_form", clear_on_submit=True):
        st.title("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        if submit:
            if username == "admin" and password == "5cf5c7ca60":  # Замени на свои данные
                st.session_state.authenticated = True
                st.query_params["auth"] = "true"  # Сохраняем состояние в URL
                st.success("Login successful")
                st.rerun()  # Перезапускаем приложение
            else:
                st.error("Incorrect username or password")
    
    st.stop()  # Останавливаем выполнение, если пользователь не залогинен
    return False