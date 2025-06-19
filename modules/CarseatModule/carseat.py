import streamlit as st
import pandas as pd
import altair as alt

def get_carseat_data(session_clever_data: dict) -> pd.DataFrame:
    """Combine carseat order tables from all uploaded files."""
    frames = []
    for d in session_clever_data.values():
        df = d.get("carseat", pd.DataFrame())
        if not df.empty:
            frames.append(df.copy())
    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame()


def _aggregate(df: pd.DataFrame, period: str) -> pd.DataFrame:
    if period == "week":
        grp = df["createdat"].dt.to_period("W").apply(lambda r: r.start_time.date())
        name = "week"
    elif period == "month":
        grp = df["createdat"].dt.to_period("M").apply(lambda r: r.start_time.date())
        name = "month"
    else:
        grp = df["createdat"].dt.date
        name = "day"
    agg = (
        df.assign(period=grp)
        .groupby(["period", "status"], as_index=False)["orderid"]
        .count()
        .pivot(index="period", columns="status", values="orderid")
        .fillna(0)
        .reset_index()
        .rename(columns={"period": name})
    )
    return agg


def _line_chart(agg: pd.DataFrame, period_col: str, title: str):
    melted = agg.melt(period_col, var_name="status", value_name="orders")
    chart = (
        alt.Chart(melted)
        .mark_line(point=True)
        .encode(
            x=alt.X(f"{period_col}:T", title=title),
            y=alt.Y("orders:Q", title="Orders"),
            color=alt.Color("status:N", title="Status"),
            tooltip=[alt.Tooltip(f"{period_col}:T"), "orders", "status"]
        )
    )
    st.altair_chart(chart, use_container_width=True)
    st.dataframe(agg, use_container_width=True)


def show(session_clever_data: dict):
    st.title("Carseat Orders Analysis")
    if not session_clever_data:
        st.warning("No data available. Please import data first.")
        return
    df = get_carseat_data(session_clever_data)
    if df.empty:
        st.warning("No carseat order data found in uploaded files.")
        return

    df = df.copy()
    if "createdat" in df.columns:
        df["createdat"] = pd.to_datetime(df["createdat"], errors="coerce")
    df = df.dropna(subset=["createdat"])
    df["status"] = df["statusid"].map({5: "Completed", 6: "Cancelled"})
    df = df[df["status"].notna()]

    day_tab, week_tab, month_tab = st.tabs(["По дням", "По неделям", "По месяцам"])

    with day_tab:
        agg = _aggregate(df, "day")
        _line_chart(agg, "day", "Day")

    with week_tab:
        agg = _aggregate(df, "week")
        _line_chart(agg, "week", "Week")

    with month_tab:
        agg = _aggregate(df, "month")
        _line_chart(agg, "month", "Month")

    st.markdown("---")
    st.subheader("Orders by User")
    user_stats = (
        df.groupby(["userid", "status"], as_index=False)["orderid"]
        .count()
        .pivot(index="userid", columns="status", values="orderid")
        .fillna(0)
        .reset_index()
        .rename(columns={"Completed": "completed", "Cancelled": "cancelled"})
    )
    st.dataframe(user_stats, use_container_width=True)

    st.markdown("---")
    st.subheader("Average Days Between Orders per User")
    df_sorted = df.sort_values(["userid", "createdat"]).copy()
    df_sorted["prev_date"] = df_sorted.groupby("userid")["createdat"].shift()
    df_sorted["days_between"] = (df_sorted["createdat"] - df_sorted["prev_date"]).dt.days
    freq = (
        df_sorted.groupby("userid")["days_between"].mean()
        .dropna()
        .reset_index()
        .rename(columns={"days_between": "avg_days_between"})
    )
    st.dataframe(freq, use_container_width=True)