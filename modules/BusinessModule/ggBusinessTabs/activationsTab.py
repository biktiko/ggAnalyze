import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
from datetime import datetime, timedelta
import json

# --- КОНФИГУРАЦИЯ ---
CONFIG_FILE = "alert_config.json"

# --- ОСНОВНАЯ ЛОГИКА АНАЛИЗА ---

def get_activity_df(merged_df, start_date, end_date, include_weekends):
    """Агрегирует данные по заказам за указанный период."""
    if include_weekends:
        days_in_period = (end_date.date() - start_date.date()).days + 1
    else:
        # Считаем только рабочие дни
        days_in_period = len(pd.bdate_range(start_date, end_date))
    
    if days_in_period <= 0:
        return pd.DataFrame(columns=["company", "TotalOrders", "AvgDailyOrders"])

    period_df = merged_df[(merged_df["date"] >= start_date) & (merged_df["date"] <= end_date)]
    
    if period_df.empty:
        return pd.DataFrame(columns=["company", "TotalOrders", "AvgDailyOrders"])

    grp = period_df.groupby("company", observed=True).agg(
        TotalOrders=("orders", "sum")
    )
    
    grp["AvgDailyOrders"] = grp["TotalOrders"] / days_in_period
    
    return grp.reset_index()


def find_passive_companies(merged_df, config, period_a_start, period_a_end, period_b_start, period_b_end):
    """Находит пассивные компании на основе правил из конфигурации и заданных периодов."""
    
    # Получаем активность за оба периода
    df_a = get_activity_df(merged_df, period_a_start, period_a_end, config["include_weekends"])
    df_b = get_activity_df(merged_df, period_b_start, period_b_end, config["include_weekends"])

    # Объединяем результаты
    comparison_df = df_a.merge(
        df_b, on="company", how="outer", suffixes=("_A", "_B")
    ).fillna(0)

    # Применяем критерии пассивности
    previous_activity = comparison_df["AvgDailyOrders_A"]
    current_activity = comparison_df["AvgDailyOrders_B"]

    abs_drop = previous_activity - current_activity
    percent_drop = np.divide(abs_drop, previous_activity, out=np.zeros_like(abs_drop), where=previous_activity!=0) * 100

    is_passive = (
        (previous_activity > config["min_activity_threshold"]) &
        (abs_drop > config["abs_drop_threshold"]) &
        (percent_drop > config["percent_drop_threshold"])
    )

    passive_df = comparison_df[is_passive].copy()
    passive_df["AbsDrop"] = abs_drop[is_passive]
    passive_df["PercentDrop"] = percent_drop[is_passive]
    
    return passive_df.sort_values("PercentDrop", ascending=False)


# --- UI И ОСНОВНАЯ ФУНКЦИЯ ---

def load_config():
    """Загружает конфигурацию из файла."""
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "percent_drop_threshold": 20.0,
            "abs_drop_threshold": 3.0,
            "min_activity_threshold": 5.0,
            "recipient_emails": "your_email@example.com\nanother_email@example.com",
            "alert_time": "15:00",
            "include_weekends": True,
        }

def save_config(config):
    """Сохраняет конфигурацию в файл."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
    st.toast("Configuration saved!", icon="✅")


def show(data: dict | None = None, filters: dict | None = None) -> None:
    st.subheader("Companies Activity Change")

    # --- Подготовка данных ---
    orders_df = data.get("orders", pd.DataFrame()).copy()
    clients_df = data.get("clients", pd.DataFrame()).copy()
    if orders_df.empty or clients_df.empty:
        st.info("No data available for analysis.")
        return
    orders_df["date"] = pd.to_datetime(orders_df["date"], errors="coerce")
    clients_df = clients_df[["userid", "company"]].dropna()
    merged = orders_df.merge(clients_df, on="userid", how="left").dropna(subset=["company", "date", "orders"])
    merged["date"] = merged["date"].dt.normalize()

    # --- Блок Конфигурации и Настроек ---
    config = load_config()
    with st.sidebar:
        st.header("⚙️ Alert Configuration")
        config["percent_drop_threshold"] = st.number_input(
            "Percentage Drop Threshold (%)", min_value=0.0, value=config["percent_drop_threshold"], step=5.0,
            help="Считать пассивной, если активность упала более чем на этот процент."
        )
        config["abs_drop_threshold"] = st.number_input(
            "Absolute Drop Threshold (orders/day)", min_value=0.0, value=config["abs_drop_threshold"], step=0.5,
            help="Считать пассивной, если среднее число заказов в день упало более чем на это значение."
        )
        config["min_activity_threshold"] = st.number_input(
            "Minimum Activity Threshold (orders/day)", min_value=0.0, value=config["min_activity_threshold"], step=1.0,
            help="Анализировать только те компании, у которых раньше было больше заказов в день, чем это значение."
        )
        config["include_weekends"] = st.toggle("Include weekends in calculations", value=config["include_weekends"])
        st.divider()
        config["recipient_emails"] = st.text_area(
            "Recipient Emails (one per line)", value=config["recipient_emails"], height=100
        )
        time_obj = datetime.strptime(config["alert_time"], "%H:%M").time()
        new_time = st.time_input("Daily alert time", value=time_obj)
        config["alert_time"] = new_time.strftime("%H:%M")
        if st.button("Save Configuration", use_container_width=True):
            save_config(config)

    # --- Блок 1: Проактивный Мониторинг ---
    st.markdown("### 🚨 Proactive Monitoring")
    
    # Вычисляем даты по умолчанию
    today = datetime.now().date()
    default_b_end = today - timedelta(days=1)
    default_b_start = default_b_end - timedelta(days=6) # Последние 7 дней
    default_a_end = default_b_start - timedelta(days=1)
    default_a_start = default_a_end - timedelta(days=13) # Предыдущие 14 дней

    with st.expander("Select periods for proactive monitoring", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            period_a_proactive = st.date_input("Previous Period (A)", value=(default_a_start, default_a_end), key="proactive_A")
        with col2:
            period_b_proactive = st.date_input("Current Period (B)", value=(default_b_start, default_b_end), key="proactive_B")

    if len(period_a_proactive) != 2 or len(period_b_proactive) != 2:
        st.warning("Please select both periods for proactive monitoring.")
        return

    pa_start, pa_end = pd.to_datetime(period_a_proactive[0]), pd.to_datetime(period_a_proactive[1])
    pb_start, pb_end = pd.to_datetime(period_b_proactive[0]), pd.to_datetime(period_b_proactive[1])

    with st.container(border=True):
        passive_companies_df = find_passive_companies(merged, config, pa_start, pa_end, pb_start, pb_end)
        if not passive_companies_df.empty:
            st.error(f"Found {len(passive_companies_df)} passive companies!")
            display_df = passive_companies_df[[
                "company", "AvgDailyOrders_A", "AvgDailyOrders_B", "AbsDrop", "PercentDrop"
            ]].rename(columns={
                "company": "Company",
                "AvgDailyOrders_A": "Avg Orders (Period A)",
                "AvgDailyOrders_B": "Avg Orders (Period B)",
                "AbsDrop": "Daily Drop (Abs)",
                "PercentDrop": "Daily Drop (%)"
            })
            columns_to_format = [
                "Avg Orders (Period A)", "Avg Orders (Period B)", "Daily Drop (Abs)", "Daily Drop (%)"
            ]
            st.dataframe(display_df.style.format("{:.2f}", subset=columns_to_format))
        else:
            st.success("No passive companies found based on the current criteria. Well done!")

    st.divider()

    # --- Блок 2: Интерактивный Анализ ---
    st.markdown("### 🔬 Interactive Analysis: Custom Periods")
    with st.expander("Select periods and format for manual comparison", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            period_a_manual = st.date_input("Period A", [], key="manual_A")
        with col2:
            period_b_manual = st.date_input("Period B", [], key="manual_B")
        format_option = st.selectbox("Display format", ["Numbers", "Percentage"])
        threshold = st.number_input("Max abs diff for plot", min_value=0.0, value=5.0, step=1.0)

    if len(period_a_manual) == 2 and len(period_b_manual) == 2:
        a0, a1 = pd.to_datetime(period_a_manual[0]), pd.to_datetime(period_a_manual[1])
        b0, b1 = pd.to_datetime(period_b_manual[0]), pd.to_datetime(period_b_manual[1])

        df_a_manual = get_activity_df(merged, a0, a1, config["include_weekends"])
        df_b_manual = get_activity_df(merged, b0, b1, config["include_weekends"])

        df = df_a_manual.merge(df_b_manual, on="company", how="outer", suffixes=("_A", "_B")).fillna(0)
        
        df["DiffNum"] = df["AvgDailyOrders_B"] - df["AvgDailyOrders_A"]
        df["DiffPercent"] = np.divide(df["DiffNum"], df["AvgDailyOrders_A"], out=np.full_like(df["DiffNum"], 100.0), where=df["AvgDailyOrders_A"]!=0) * 100
        
        diff_col = "DiffNum" if format_option == "Numbers" else "DiffPercent"
        df["DiffPlot"] = df[diff_col].clip(lower=-threshold, upper=threshold)
        
        df = df.sort_values(diff_col, ascending=True, ignore_index=True)

        chart = alt.Chart(df).mark_bar().encode(
            y=alt.Y("company:N", sort=df["company"].tolist()),
            x=alt.X("DiffPlot:Q", title="Δ Activity"),
            color=alt.condition(alt.datum[diff_col] >= 0, alt.value("green"), alt.value("red")),
            tooltip=[
                "company",
                alt.Tooltip("AvgDailyOrders_A:Q", title="Avg Orders A", format=".2f"),
                alt.Tooltip("AvgDailyOrders_B:Q", title="Avg Orders B", format=".2f"),
                alt.Tooltip(f"{diff_col}:Q", title=f"Difference ({format_option})", format=".2f"),
            ],
        )
        st.altair_chart(chart, use_container_width=True)
        with st.expander("Details"):
            st.dataframe(df)
