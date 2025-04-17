import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
# Тарифы Yandex и gg
Yandex_tariffs = {
    "Старт": {"min_cost": 300, "free_min": 2.5, "free_km": 1, "city_km": 60, "city_min": 15},
    "Комфорт": {"min_cost": 400, "free_min": 2.5, "free_km": 1, "city_km": 80, "city_min": 20},
    "Комфорт+": {"min_cost": 500, "free_min": 2.5, "free_km": 1, "city_km": 100, "city_min": 25},
    "Бизнес": {"min_cost": 700, "free_min": 2.5, "free_km": 1, "city_km": 130, "city_min": 30},
}

gg_tariffs = {
    "ggEconom": {"min_cost": 400, "free_min": 15, "free_km": 1, "city_km": 100, "city_min": 20},
    "gg": {"min_cost": 600, "free_min": 15, "free_km": 1, "city_km": 100, "city_min": 20},
    "ggSpecial": {"min_cost": 800, "free_min": 15, "free_km": 1, "city_km": 150, "city_min": 30},
}

# Функция расчёта стоимости поездки для Yandex
def calc_cost_yandex(tariff, km, minutes, surge):
    cost = tariff['min_cost'] + surge
    extra_km = max(0, km - tariff['free_km'])
    extra_min = max(0, minutes - tariff['free_min'])
    cost += extra_km * tariff['city_km'] + extra_min * tariff['city_min']
    return np.round(cost, -1)

# Функция расчёта стоимости поездки для gg (округляет километры вверх)
def calc_cost_gg(tariff, km, minutes, surge):
    cost = tariff['min_cost'] + surge
    km = np.ceil(km) if km % 1 >= 0.1 else np.floor(km)
    extra_km = max(0, km - tariff['free_km'])
    extra_min = max(0, minutes - tariff['free_min'])
    cost += extra_km * tariff['city_km'] + extra_min * tariff['city_min']
    return round(cost / 100) * 100

# Streamlit интерфейс
def comparison_show():

    st.title("Сравнение тарифов ")

    col1, col2 = st.columns(2)

    with col1:
        km = st.number_input("🛣️ Расстояние (км)", min_value=0.1, value=5.0, step=0.1)
        surge_gg = st.number_input("Surge price gg", min_value=0, step=50, value=0)
        is_corporate = st.checkbox("🏢 Корпоративная поездка")

    with col2:
        minutes = st.number_input("⏳ Время поездки (мин)", min_value=1, value=10, step=1)
        surge_yandex = st.number_input("Surge price Yandex", min_value=0, step=50, value=0)

    promo_code = st.number_input("🎟️ Промокод gg")

    results = []

    for name, tariff in Yandex_tariffs.items():
        cost = calc_cost_yandex(tariff, km, minutes, surge_yandex)
        if is_corporate:
            cost *= 1.12
        results.append({"Сервис": "Yandex", "Тариф": name, "Цена": round(cost)})

    for name, tariff in gg_tariffs.items():
        cost = calc_cost_gg(tariff, km, minutes, surge_gg) - promo_code
        results.append({"Сервис": "gg", "Тариф": name, "Цена": cost})

    st.subheader("💰 Стоимость поездок:")
    df = pd.DataFrame(results)
    df_sorted = df.sort_values(by="Цена")
    st.dataframe(df_sorted, use_container_width=True)

    st.subheader("📊 Cравнение тарифов:")


    chart = alt.Chart(df_sorted).mark_bar().encode(
        x=alt.X('Цена', title='Цена (֏)', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Тариф:N', title='Тариф', sort='-x'),
        color=alt.Color('Сервис:N', scale=alt.Scale(scheme='category10')),
        tooltip=['Сервис', 'Тариф', 'Цена']
    ).properties(
        width=700,
        height=400
    ).interactive()

    st.altair_chart(chart, use_container_width=True)