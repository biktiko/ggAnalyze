import streamlit as st
import pandas as pd
from datetime import timedelta


def _parse_interval_seconds(val: str) -> float:
    """Convert textual interval like '0 years 0 mons 0 days 0 hours 3 mins 10 secs' to seconds."""
    if pd.isna(val):
        return 0.0
    import re
    values = {"years": 0, "mons": 0, "days": 0, "hours": 0, "mins": 0, "secs": 0.0}
    for num, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(years?|mons?|days?|hours?|mins?|secs?)", str(val).lower()):
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
    td = timedelta(days=values["days"], hours=values["hours"], minutes=values["mins"], seconds=values["secs"])
    return td.total_seconds()


def _calc_stats(series: pd.Series) -> dict:
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return {"Average": None, "Median": None, "Skew": None, "stDeviation": None, "Min": None, "Max": None}
    return {
        "Average": series.mean(),
        "Median": series.median(),
        "Skew": series.skew() if len(series) > 2 else 0,
        "stDeviation": series.std(),
        "Min": series.min(),
        "Max": series.max(),
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

    orders["accepted_seconds"] = orders.get("accepted_interval").apply(_parse_interval_seconds)
    orders["arrived_minutes"] = orders.get("arrived_interval").apply(_parse_interval_seconds) / 60.0
    orders["distance"] = pd.to_numeric(orders.get("distance"), errors="coerce")
    orders["fare"] = pd.to_numeric(orders.get("fare"), errors="coerce")

    if not cancels.empty:
        cancels = cancels[cancels.get("userid").isin(orders.get("userid"))]
        cancels["createdat"] = pd.to_datetime(cancels.get("createdat"), errors="coerce")
        cancels["canceldate"] = pd.to_datetime(cancels.get("canceldate"), errors="coerce")
        cancels["wait_sec"] = (cancels["canceldate"] - cancels["createdat"]).dt.total_seconds()
    else:
        cancels = pd.DataFrame(columns=["userid", "wait_sec"])

    with st.expander("Filters", expanded=True):
        min_date = orders["orderdate1"].min().date() if "orderdate1" in orders.columns else None
        max_date = orders["orderdate1"].max().date() if "orderdate1" in orders.columns else None
        date_range = st.date_input("Date range", (min_date, max_date)) if min_date else ()
        profile_options = sorted(orders.get("profileid", pd.Series(dtype=str)).dropna().astype(str).unique())
        selected_profiles = st.multiselect("Profiles", profile_options)

    if date_range and len(date_range) == 2 and "orderdate1" in orders.columns:
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        orders = orders[(orders["orderdate1"] >= start) & (orders["orderdate1"] <= end)]
    if selected_profiles and "profileid" in orders.columns:
        orders = orders[orders["profileid"].astype(str).isin(selected_profiles)]
    cancels = cancels[cancels["userid"].isin(orders["userid"])]

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
        merged["accepted_with_cancel"] = merged["accepted_seconds"] + merged["wait_sec"].fillna(0)
    else:
        merged = orders.copy()
        merged["accepted_with_cancel"] = merged["accepted_seconds"]

    stats_incl = _calc_stats(merged["accepted_with_cancel"])

    # Prepare results for display
    metrics_df = pd.DataFrame(stats_excl).T
    metrics_df_incl = pd.DataFrame([stats_incl]).T
    metrics_df_incl.columns = ["Including cancels"]

    st.markdown("### Metrics without cancels")
    st.dataframe(metrics_df)

    st.markdown("### Accepted time including cancels")
    st.dataframe(metrics_df_incl)
