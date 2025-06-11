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
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return {
            "Average": None,
            "Median": None,
            "Skew": None,
            "stDeviation": None,
            "Min": None,
            "Max": None,
        }
    return {
        "Average": series.mean().__round__(1),
        "Median": series.median().__round__(1),
        "Skew": series.skew() if len(series) > 2 else 0,
        "stDeviation": series.std(),
        "Min": series.min().__round__(0),
        "Max": series.max().__round__(0),
    }


def show(data: dict, filters: dict) -> None:
    st.subheader("Service Metrics")

    orders = data.get("serveOrders", pd.DataFrame()).copy()
    cancels = data.get("cancellations", pd.DataFrame()).copy()

    if orders.empty:
        st.info("No serve order history available.")
        return

    # basic parsing
    if "orderdate1" in orders.columns:
        orders["orderdate1"] = pd.to_datetime(orders["orderdate1"], errors="coerce")

    acc_col = (
        "acceptedinterval"
        if "acceptedinterval" in orders.columns
        else "accepted_interval"
    )
    arr_col = (
        "arrivedinterval" if "arrivedinterval" in orders.columns else "arrived_interval"
    )
    orders["accepted_seconds"] = orders.get(acc_col).apply(_parse_interval_seconds)
    orders["arrived_minutes"] = (
        orders.get(arr_col).apply(_parse_interval_seconds) / 60.0
    )
    orders["distance"] = pd.to_numeric(orders.get("distance"), errors="coerce")
    orders["fare"] = pd.to_numeric(orders.get("fare"), errors="coerce")


    if not cancels.empty:
        st.write('cancels')
        st.write(cancels)
        cancels = cancels[cancels["mobile"].isin(orders["usermobile"])]

        date_col = "date" if "date" in cancels.columns else "createdAt"
        cancel_col = "canceldate" if "canceldate" in cancels.columns else "cancelDate"
        cancels["date"] = pd.to_datetime(cancels.get(date_col), errors="coerce")
        cancels["canceldate"] = pd.to_datetime(cancels.get(cancel_col), errors="coerce")
        cancels["wait_sec"] = (
            cancels["canceldate"] - cancels["date"]
        ).dt.total_seconds()
    else:
        cancels = pd.DataFrame(columns=["userid", "wait_sec"])

    with st.expander("Filters", expanded=True):
        min_date = (
            orders["orderdate1"].min().date()
            if "orderdate1" in orders.columns
            else None
        )
        max_date = (
            orders["orderdate1"].max().date()
            if "orderdate1" in orders.columns
            else None
        )
        date_range = (
            st.date_input("Date range", (min_date, max_date)) if min_date else ()
        )
        tariff_options = sorted(
            orders.get("tariff", pd.Series(dtype=str)).dropna().astype(str).unique()
        )
        selected_tariffs = st.multiselect("Tariffs", tariff_options)
        col1, col2 = st.columns(2)
        with col1:
            min_distance = st.number_input(
                "Min distance",
                value=float(
                    orders["distance"].min()
                    if not orders["distance"].dropna().empty
                    else 0
                ),
            )
            min_fare = st.number_input(
                "Min fare",
                value=float(
                    orders["fare"].min() if not orders["fare"].dropna().empty else 0
                ),
            )
        with col2:
            max_distance = st.number_input(
                "Max distance",
                value=float(
                    orders["distance"].max()
                    if not orders["distance"].dropna().empty
                    else 0
                ),
            )
            max_fare = st.number_input(
                "Max fare",
                value=float(
                    orders["fare"].max() if not orders["fare"].dropna().empty else 0
                ),
            )
        min_cancel_wait = st.number_input(
            "Exclude cancels shorter than (sec)", value=0, step=10
        )

    if date_range and len(date_range) == 2 and "orderdate1" in orders.columns:
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        orders = orders[(orders["orderdate1"] >= start) & (orders["orderdate1"] <= end)]

    if selected_tariffs:
        orders = orders[orders["tariff"].astype(str).isin(selected_tariffs)]

    orders = orders[
        (orders["distance"] >= min_distance) & (orders["distance"] <= max_distance)
    ]
    orders = orders[(orders["fare"] >= min_fare) & (orders["fare"] <= max_fare)]

    if min_cancel_wait > 0:
        cancels = cancels[cancels["wait_sec"] >= min_cancel_wait]

    # Stats excluding cancels
    stats_excl = {
        "Accepted time (sec)": _calc_stats(orders["accepted_seconds"]),
        "Arrived time (min)": _calc_stats(orders["arrived_minutes"]),
        "Distance (km)": _calc_stats(orders["distance"]),
        "Fare (dram)": _calc_stats(orders["fare"]),
    }

    # Stats including cancels (add waiting time)
    if not cancels.empty:
        merged = orders.merge(cancels[["userid", "wait_sec"]], on="userid", how="left")
        merged["accepted_with_cancel"] = merged["accepted_seconds"] + merged[
            "wait_sec"
        ].fillna(0)
    else:
        merged = orders.copy()
        merged["accepted_with_cancel"] = merged["accepted_seconds"]

    stats_incl = _calc_stats(merged["accepted_with_cancel"])

    # Prepare results for display
    metrics_df = pd.DataFrame(stats_excl).T
    metrics_df_incl = pd.DataFrame([stats_incl]).T
    metrics_df_incl.columns = ["Including cancels"]

    if not cancels.empty:
        st.markdown("### Metrics without cancels")
        st.dataframe(metrics_df)

    st.markdown("### Accepted time including cancels")
    st.dataframe(metrics_df_incl)

    # ----------- Charts -----------
    st.markdown("### Accepted Seconds Distribution")
    acc_chart = (
        alt.Chart(orders)
        .mark_bar()
        .encode(
            alt.X("accepted_seconds:Q", bin=alt.Bin(step=30), title="Accepted sec"),
            y="count()",
        )
    )
    st.altair_chart(acc_chart, use_container_width=True)

    st.markdown("### Arrival Minutes Distribution")
    arr_chart = (
        alt.Chart(orders)
        .mark_bar()
        .encode(
            alt.X("arrived_minutes:Q", bin=alt.Bin(step=1), title="Arrived min"),
            y="count()",
        )
    )
    st.altair_chart(arr_chart, use_container_width=True)

    if "orderdate1" in orders.columns:
        st.markdown("### Orders by Hour")
        hour_df = (
            orders.groupby(orders["orderdate1"].dt.hour)
            .size()
            .reset_index(name="count")
        )
        hour_df.rename(columns={"orderdate1": "hour"}, inplace=True)
        chart_hour = (
            alt.Chart(hour_df)
            .mark_bar()
            .encode(x=alt.X("hour:O", title="Hour"), y="count")
        )
        st.altair_chart(chart_hour, use_container_width=True)

    if not cancels.empty:
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
            .encode(x=alt.X("hour:O", title="Hour"), y="count")
        )
        st.altair_chart(chart_cancel_hour, use_container_width=True)

        st.markdown("### Cancellation Wait Distribution")
        wait_chart = (
            alt.Chart(cancels)
            .mark_bar()
            .encode(
                alt.X("wait_sec:Q", bin=alt.Bin(step=30), title="Wait seconds"),
                y="count()",
            )
        )
        st.altair_chart(wait_chart, use_container_width=True)

        buckets = pd.cut(
            cancels["wait_sec"],
            [0, 30, 60, 120, float("inf")],
            right=False,
            labels=["<30", "30-60", "60-120", ">120"],
        )
        bucket_stats = buckets.value_counts().sort_index().reset_index()
        bucket_stats.columns = ["wait_range", "count"]
        st.dataframe(bucket_stats)

    st.write("orders history")
    st.write(orders)

    st.write("cancellations history")
    st.write(cancels)
