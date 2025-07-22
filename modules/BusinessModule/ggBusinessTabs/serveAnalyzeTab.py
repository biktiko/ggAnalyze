import streamlit as st
import pandas as pd
import altair as alt
from datetime import timedelta


def _parse_interval_seconds(val: str) -> float:
    """Convert textual interval like '0 years 0 mons 0 days 0 hours 3 mins 10 secs' to seconds."""
    if pd.isna(val):
        return 0.0
    import re

    values = {"years": 0, "mons": 0, "days": 0, "hours": 0, "mins": 0, "secs": 0.0}
    for num, unit in re.findall(
        r"(\d+(?:\.\d+)?)\s*(years?|mons?|days?|hours?|mins?|secs?)", str(val).lower()
    ):
        num = float(num)
        if unit.startswith("year"):
            values["days"] += num * 365
        elif unit.startswith("mon"):
            values["days"] += num * 30
        elif unit.startswith("day"):
            values["days"] += num
        elif unit.startswith("hour"):
            values["hours"] += num
        elif unit.startswith("min"):
            values["mins"] += num
        elif unit.startswith("sec"):
            values["secs"] += num
    td = timedelta(
        days=values["days"],
        hours=values["hours"],
        minutes=values["mins"],
        seconds=values["secs"],
    )
    return td.total_seconds()


def _calc_stats(series: pd.Series) -> dict:
    """Calculates descriptive statistics for a series, including quartiles."""
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return {
            "Sum": None,
            "Average": None,
            "Min": None,
            "Q1 (25%)": None,
            "Median (50%)": None,
            "Q3 (75%)": None,
            "Max": None,
            "IQR": None,
            "Skew": None,
            "stDeviation": None,
        }

    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)

    return {
        "Sum": series.sum().__round__(0),
        "Average": series.mean().__round__(1),
        "Min": series.min().__round__(0),
        "Q1 (25%)": q1.__round__(1),
        "Median (50%)": series.median().__round__(1),
        "Q3 (75%)": q3.__round__(1),
        "Max": series.max().__round__(0),
        "IQR": (q3 - q1).__round__(1),
        "Skew": series.skew() if len(series) > 2 else 0,
        "stDeviation": series.std().__round__(4),
    }


def show(data: dict, filters: dict) -> None:
    st.subheader("Service Metrics")

    orders = data.get("serveOrders", pd.DataFrame()).copy()
    cancels = data.get("cancellations", pd.DataFrame()).copy()

    if orders.empty:
        st.info("No serve order history available.")
        return

    # --- Data Preparation ---
    if "orderdate1" in orders.columns:
        orders["orderdate1"] = pd.to_datetime(orders["orderdate1"], errors="coerce")

    acc_col = "acceptedinterval" if "acceptedinterval" in orders.columns else "accepted_interval"
    arr_col = "arrivedinterval" if "arrivedinterval" in orders.columns else "arrived_interval"
    orders["accepted_seconds"] = orders.get(acc_col).apply(_parse_interval_seconds)
    orders["arrived_minutes"] = (orders.get(arr_col).apply(_parse_interval_seconds) / 60.0)
    orders["distance"] = pd.to_numeric(orders.get("distance"), errors="coerce")
    orders["fare"] = pd.to_numeric(orders.get("fare"), errors="coerce")

    if not cancels.empty:
        if 'userid' in orders.columns and 'userid' in cancels.columns:
            cancels = cancels[cancels["userid"].isin(orders["userid"])]
        date_col = "date" if "date" in cancels.columns else "createdAt"
        cancel_col = "canceldate" if "canceldate" in cancels.columns else "cancelDate"
        if date_col in cancels.columns and cancel_col in cancels.columns:
            cancels["date"] = pd.to_datetime(cancels.get(date_col), errors="coerce")
            cancels["canceldate"] = pd.to_datetime(cancels.get(cancel_col), errors="coerce")
            cancels["wait_sec"] = (cancels["canceldate"] - cancels["date"]).dt.total_seconds()
    else:
        cancels = pd.DataFrame(columns=["userid", "wait_sec"])

    # --- Filters UI ---
    with st.expander("Filters", expanded=True):
        min_date = (orders["orderdate1"].min().date() if "orderdate1" in orders.columns and not orders["orderdate1"].dropna().empty else None)
        max_date = (orders["orderdate1"].max().date() if "orderdate1" in orders.columns and not orders["orderdate1"].dropna().empty else None)
        date_range = (st.date_input("Date range", (min_date, max_date)) if min_date and max_date else ())
        tariff_options = sorted(orders.get("tariff", pd.Series(dtype=str)).dropna().astype(str).unique())
        selected_tariffs = st.multiselect("Tariffs", tariff_options)
        business_options = sorted(orders.get("businessusername", pd.Series(dtype=str)).dropna().astype(str).unique())
        profiles_options = sorted(orders.get("profilename", pd.Series(dtype=str)).dropna().astype(str).unique())
        col1, col2 = st.columns(2)
        with col1:
            selected_profiles = st.multiselect("profiles", profiles_options)
            min_distance = st.number_input("Min distance", value=float(orders["distance"].min() if not orders["distance"].dropna().empty else 0))
            min_fare = st.number_input("Min fare", value=float(orders["fare"].min() if not orders["fare"].dropna().empty else 0))
        with col2:
            selected_business = st.multiselect("Business usernames", business_options)
            max_distance = st.number_input("Max distance", value=float(orders["distance"].max() if not orders["distance"].dropna().empty else 0))
            max_fare = st.number_input("Max fare", value=float(orders["fare"].max() if not orders["fare"].dropna().empty else 0))
        min_cancel_wait = st.number_input("Exclude cancels shorter than (sec)", value=0, step=10)


    # --- Apply Filters ---
    if date_range and len(date_range) == 2 and "orderdate1" in orders.columns:
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        orders = orders[(orders["orderdate1"] >= start) & (orders["orderdate1"] <= end)]
    if selected_business:
        orders = orders[orders["businessusername"].astype(str).isin(selected_business)]
    if selected_profiles:
        orders = orders[orders["profilename"].astype(str).isin(selected_profiles)]
    if selected_tariffs:
        orders = orders[orders["tariff"].astype(str).isin(selected_tariffs)]
    if "distance" in orders.columns:
        orders = orders[(orders["distance"] >= min_distance) & (orders["distance"] <= max_distance)]
    if "fare" in orders.columns:
        orders = orders[(orders["fare"] >= min_fare) & (orders["fare"] <= max_fare)]
    if min_cancel_wait > 0 and "wait_sec" in cancels.columns:
        cancels = cancels[cancels["wait_sec"] >= min_cancel_wait]
    
    if 'userid' in orders.columns and 'userid' in cancels.columns:
        cancels = cancels[cancels["userid"].isin(orders["userid"])]

    # --- Calculations ---
    stats_excl = {
        "Accepted time (sec)": _calc_stats(orders["accepted_seconds"]),
        "Arrived time (min)": _calc_stats(orders["arrived_minutes"]),
        "Distance (km)": _calc_stats(orders["distance"]),
        "Fare (dram)": _calc_stats(orders["fare"]),
    }
    combined_series = []
    if "accepted_seconds" in orders.columns:
        combined_series.append(pd.to_numeric(orders["accepted_seconds"], errors="coerce"))
    if "wait_sec" in cancels.columns:
        combined_series.append(pd.to_numeric(cancels["wait_sec"], errors="coerce"))
    
    combined = pd.concat(combined_series, ignore_index=True) if combined_series else pd.Series()

    stats_incl = _calc_stats(combined)
    metrics_df = pd.DataFrame(stats_excl).T
    metrics_df.loc["Accepted time including cancels"] = stats_incl

    # --- Display Metrics ---
    st.markdown("### Key Metrics")
    display_columns = ["Min", "Q1 (25%)", "Median (50%)", "Q3 (75%)", "Max", "IQR", "Average", "Sum", "stDeviation", "Skew"]
    # Ensure all columns exist before trying to display them
    existing_display_columns = [col for col in display_columns if col in metrics_df.columns]
    st.dataframe(metrics_df[existing_display_columns])

    order_count = len(orders)
    cancel_count = len(cancels)
    unique_mobiles = orders["usermobile"].nunique() if "usermobile" in orders.columns else 0
    col_a, col_b, col_c = st.columns(3)
    with col_a: st.metric("Total rides", order_count)
    with col_b: st.metric("Total cancels", cancel_count)
    with col_c: st.metric("Unique users with orders", unique_mobiles)

    # ----------- Charts -----------
    st.markdown("---")
    st.markdown("### Visual Analysis")
    
    st.markdown("#### Arrival Time Spread (Box Plot)")
    st.markdown("Эта диаграмма показывает медиану (линия), центральные 50% данных (ящик) и выбросы (точки). Идеально для оценки разброса без влияния аномалий.")
    if not orders.empty and "arrived_minutes" in orders.columns:
        boxplot_arr = alt.Chart(orders).mark_boxplot(extent='min-max').encode(
            x=alt.X('arrived_minutes:Q', title="Arrived Time (min)")
        ).properties(width=600)
        st.altair_chart(boxplot_arr, use_container_width=True)

    st.markdown("#### Distance vs. Fare")
    st.markdown("Каждая точка - это поездка. Этот график помогает увидеть зависимость между дистанцией и стоимостью.")
    if not orders.empty and "distance" in orders.columns and "fare" in orders.columns:
        scatter_fare_dist = alt.Chart(orders).mark_circle(size=60, opacity=0.5).encode(
            x=alt.X('distance:Q', title='Distance (km)'),
            y=alt.Y('fare:Q', title='Fare (dram)'),
            tooltip=['distance', 'fare', 'tariff']
        ).interactive()
        st.altair_chart(scatter_fare_dist, use_container_width=True)

    st.markdown("#### Distributions (Histograms)")
    if "accepted_seconds" in orders.columns:
        acc_chart = (alt.Chart(orders).mark_bar().encode(alt.X("accepted_seconds:Q", bin=alt.Bin(maxbins=50), title="Accepted sec"), y="count()"))
        st.altair_chart(acc_chart, use_container_width=True)
    if "arrived_minutes" in orders.columns:
        arr_chart = (alt.Chart(orders).mark_bar().encode(alt.X("arrived_minutes:Q", bin=alt.Bin(maxbins=50), title="Arrived min"), y="count()"))
        st.altair_chart(arr_chart, use_container_width=True)

    with st.expander("Detailed Metrics", expanded=False):
        if "businessusername" in orders.columns:
            tab_bus, tab_prof = st.tabs(["businessusername", "profilename"])
            df_bus = (orders.groupby("businessusername", as_index=False).size().rename(columns={"size": "order_count"}).sort_values("order_count", ascending=False))
            if "usermobile" in orders.columns:
                usermobiles = orders.groupby("businessusername")["usermobile"].first().reset_index()
                df_bus = df_bus.merge(usermobiles, on="businessusername", how="left")
                df_bus = df_bus[["businessusername", "usermobile", "order_count"]]
            
            if "profilename" in orders.columns:
                df_prof = (orders.groupby("profilename", as_index=False).size().rename(columns={"size": "order_count"}).sort_values("order_count", ascending=False))
                with tab_prof:
                    st.bar_chart(df_prof.set_index("profilename")['order_count'])
                    st.dataframe(df_prof)

            with tab_bus:
                st.bar_chart(df_bus.set_index("businessusername")["order_count"])
                st.dataframe(df_bus)

    if "orderdate1" in orders.columns:
        st.markdown("### Orders by Hour")
        hour_df = (orders.groupby(orders["orderdate1"].dt.hour).size().reset_index(name="count"))
        hour_df.rename(columns={"orderdate1": "hour"}, inplace=True)
        chart_hour = (alt.Chart(hour_df).mark_bar().encode(x=alt.X("hour:O", title="Hour of Day"), y="count"))
        st.altair_chart(chart_hour, use_container_width=True)
    
    if not cancels.empty and "canceldate" in cancels.columns:
        st.markdown("### Cancels by Hour")
        cancel_hour = (
            cancels.groupby(cancels["canceldate"].dt.hour)
            .size()
            .reset_index(name="count")
        )
        cancel_hour.rename(columns={"canceldate": "hour"}, inplace=True)
        chart_cancel_hour = (
            alt.Chart(cancel_hour)
            .mark_bar()
            .encode(x=alt.X("hour:O", title="Hour of Day"), y="count")
        )
        st.altair_chart(chart_cancel_hour, use_container_width=True)

        if "wait_sec" in cancels.columns:
            st.markdown("### Cancellation Wait Distribution")
            wait_chart = (
                alt.Chart(cancels)
                .mark_bar()
                .encode(
                    alt.X("wait_sec:Q", bin=alt.Bin(maxbins=40), title="Wait seconds"),
                    y="count()",
                )
            )
            st.altair_chart(wait_chart, use_container_width=True)

            buckets = pd.cut(
                cancels["wait_sec"],
                [0, 30, 60, 120, 300, float("inf")],
                right=False,
                labels=["<30s", "30-60s", "60-120s", "120-300s", ">300s"],
            )
            bucket_stats = buckets.value_counts().sort_index().reset_index()
            bucket_stats.columns = ["wait_range", "count"]
            st.dataframe(bucket_stats)

    st.markdown("---")
    with st.expander("Raw Data History"):
        st.write("Orders History")
        st.dataframe(orders)

        st.write("Cancellations History")
        st.dataframe(cancels)
