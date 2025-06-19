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
    # Group by selected period
    if period == "week":
        grp = df["date"].dt.to_period("W").apply(lambda r: r.start_time.date())
        name = "week"
    elif period == "month":
        grp = df["date"].dt.to_period("M").apply(lambda r: r.start_time.date())
        name = "month"
    else:
        grp = df["date"].dt.date
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
    # Prepare and render line chart
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
        .properties(height=300)
    )
    st.altair_chart(chart, use_container_width=True)


def show(session_clever_data: dict):
    st.title("Carseat Orders Analysis")

    # Load and preprocess data
    if not session_clever_data:
        st.warning("No data available. Please import data first.")
        return
    df = get_carseat_data(session_clever_data)
    if df.empty:
        st.warning("No carseat order data found in uploaded files.")
        return

    df = df.copy()
    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    df = df.dropna(subset=["date"])
    df["status"] = df["statusid"].map({5: "Completed", 6: "Cancelled"})
    df = df[df["status"].notna()]

    # FILTERS
    with st.expander("Filters", expanded=True):
        # Date range filter
        min_date = df["date"].min().date()
        max_date = df["date"].max().date()
        date_range = st.date_input("Period", value=(min_date, max_date),
                                   min_value=min_date, max_value=max_date)
        # Status filter
        statuses = df["status"].unique().tolist()
        selected_status = st.multiselect("Status", options=statuses, default=statuses)
        # Period selection
        period = st.radio("Group by", options=["day", "week", "month"], index=0,
                          format_func=lambda x: {"day":"Day", "week":"Week","month":"Month"}[x])

    # Apply filters
    start, end = date_range
    filtered = df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end) &
                  (df["status"].isin(selected_status))]

    filteredWithoutStatus = df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end)]
    # Show statistics under filters
    col1, col2 = st.columns(2)

    st.subheader("Filtered statistics")
    completed = (filteredWithoutStatus["status"] == "Completed").sum()
    cancelled = (filteredWithoutStatus["status"] == "Cancelled").sum()
    
    with col1:
        st.metric("Completed", completed)
    
    with col2:
        st.metric("Cancelled", cancelled)

    # Chart and tables under filters
    agg = _aggregate(filtered, period)
    _line_chart(agg, period, {"day":"День", "week":"Неделя", "month":"Месяц"}[period])
    st.dataframe(agg, use_container_width=True)

    # Orders by user
    st.subheader("Orders by User ")
    user_stats = (
        filteredWithoutStatus.groupby(["userid", "status"], as_index=False)["orderid"]
        .count()
        .pivot(index="userid", columns="status", values="orderid")
        .fillna(0)
        .reset_index()
        .rename(columns={"Completed": "completed", "Cancelled": "cancelled"})
    )
    st.dataframe(user_stats, use_container_width=True)

 # Average Days Between Orders per User
    st.subheader("Average Days Between Orders per User")
    df_sorted = filteredWithoutStatus.sort_values(["userid","date"]).copy()
    df_sorted["prev_date"] = df_sorted.groupby("userid")["date"].shift()
    df_sorted["days_between"] = (df_sorted["date"] - df_sorted["prev_date"]).dt.days

    # Completed orders count
    df_completed = df_sorted[df_sorted["status"]=="Completed"]
    orders_count = df_completed.groupby("userid")["orderid"].count().reset_index(name="completed_orders")

    # Avg days
    freq = df_sorted.groupby("userid")["days_between"].mean().dropna().reset_index().rename(columns={"days_between":"avg_days_between"})
    freq = freq.merge(orders_count, on="userid", how="left").fillna({"completed_orders":0})
    # Exclude users with <=1 completed orders
    freq = freq[freq["completed_orders"]>1]

    st.dataframe(freq, use_container_width=True)

    # Raw data
    st.markdown("---")
    st.subheader("Carseat Data")
    st.dataframe(df, use_container_width=True, hide_index=True)
