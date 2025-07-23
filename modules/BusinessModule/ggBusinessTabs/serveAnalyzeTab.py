import streamlit as st
import pandas as pd
import altair as alt
from datetime import timedelta
import json
import ast

# --- HELPER FUNCTIONS ---

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
        if unit.startswith("year"): values["days"] += num * 365
        elif unit.startswith("mon"): values["days"] += num * 30
        elif unit.startswith("day"): values["days"] += num
        elif unit.startswith("hour"): values["hours"] += num
        elif unit.startswith("min"): values["mins"] += num
        elif unit.startswith("sec"): values["secs"] += num
    td = timedelta(days=values["days"], hours=values["hours"], minutes=values["mins"], seconds=values["secs"])
    return td.total_seconds()

def _calc_stats(series: pd.Series) -> dict:
    """Calculates descriptive statistics for a series, including quartiles."""
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return {
            "Sum": None, "Average": None, "Min": None, "Q1 (25%)": None,
            "Median (50%)": None, "Q3 (75%)": None, "Max": None, "IQR": None,
            "Skew": None, "stDeviation": None,
        }
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    return {
        "Sum": series.sum().__round__(0), "Average": series.mean().__round__(1),
        "Min": series.min().__round__(0), "Q1 (25%)": q1.__round__(1),
        "Median (50%)": series.median().__round__(1), "Q3 (75%)": q3.__round__(1),
        "Max": series.max().__round__(0), "IQR": (q3 - q1).__round__(1),
        "Skew": series.skew() if len(series) > 2 else 0,
        "stDeviation": series.std().__round__(4),
    }

def _create_company_mapping(users_df: pd.DataFrame) -> dict:
    """Creates a dictionary to map userid to a company."""
    if users_df.empty or 'users' not in users_df.columns:
        return {}
        
    def parse_list_safely(x):
        try:
            return ast.literal_eval(x)
        except (ValueError, SyntaxError):
            return []

    users_df["parsed_users"] = users_df["users"].apply(parse_list_safely)
    mapping = {}
    for _, row in users_df.iterrows():
        company = row["company"]
        for user_id in row["parsed_users"]:
            mapping[user_id] = company
    return mapping

def _group_cancellations(cancels_df: pd.DataFrame) -> pd.DataFrame:
    """Groups cancellations by user and day, summing the wait time."""
    if cancels_df.empty or "canceldate" not in cancels_df.columns:
        return pd.DataFrame()

    cancels_df_sorted = cancels_df.sort_values(by=['userid', 'canceldate'])
    grouped = cancels_df_sorted.groupby([
        cancels_df_sorted['userid'],
        cancels_df_sorted['canceldate'].dt.date
    ]).agg(
        session_start_time=('canceldate', 'first'),
        total_wait_sec=('wait_sec', 'sum'),
        cancellations_in_session=('userid', 'size'),
        company=('company', 'first')
    ).reset_index()
    return grouped


# --- MAIN SHOW FUNCTION ---

def show(data: dict) -> None:
    
    # --- Data Loading and Initial Preparation ---
    orders = data.get("serveOrders", pd.DataFrame()).copy()
    cancels = data.get("cancellations", pd.DataFrame()).copy()
    users_df = data.get("users", pd.DataFrame()).copy()

    if orders.empty:
        st.info("No serve order history available.")
        return

    company_mapping = _create_company_mapping(users_df)
    orders['company'] = orders['userid'].map(company_mapping)
    if not cancels.empty:
        cancels['company'] = cancels['userid'].map(company_mapping)

    if "orderdate1" in orders.columns:
        orders["orderdate1"] = pd.to_datetime(orders["orderdate1"], errors="coerce")

    # --- Top Level Filters ---
    st.markdown("### Filters")
    all_companies = sorted(
        [comp for comp in pd.concat([orders.get('company', pd.Series()), cancels.get('company', pd.Series())]).dropna().unique()]
    )
    
    top_col1, top_col2 = st.columns(2)
    with top_col1:
        min_date_overall = orders["orderdate1"].min().date() if not orders["orderdate1"].dropna().empty else None
        max_date_overall = orders["orderdate1"].max().date() if not orders["orderdate1"].dropna().empty else None
        date_range = st.date_input("Date range", (min_date_overall, max_date_overall), key="main_date_filter") if min_date_overall and max_date_overall else ()
    with top_col2:
        selected_companies = st.multiselect("Filter by Companies", all_companies, default=[])

    # Apply main filters
    if date_range and len(date_range) == 2:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        orders = orders[(orders["orderdate1"] >= start_date) & (orders["orderdate1"] <= end_date)]
    
    if selected_companies:
        orders = orders[orders['company'].isin(selected_companies)]
        if not cancels.empty:
            cancels = cancels[cancels['company'].isin(selected_companies)]

    # --- Secondary Data Preparation ---
    acc_col = "acceptedinterval" if "acceptedinterval" in orders.columns else "accepted_interval"
    arr_col = "arrivedinterval" if "arrivedinterval" in orders.columns else "arrived_interval"
    orders["accepted_seconds"] = orders.get(acc_col).apply(_parse_interval_seconds)
    orders["arrived_minutes"] = (orders.get(arr_col).apply(_parse_interval_seconds) / 60.0)
    orders["distance"] = pd.to_numeric(orders.get("distance"), errors="coerce")
    orders["fare"] = pd.to_numeric(orders.get("fare"), errors="coerce")

    if not cancels.empty:
        date_col = "date" if "date" in cancels.columns else "createdAt"
        cancel_col = "canceldate" if "canceldate" in cancels.columns else "cancelDate"
        if date_col in cancels.columns and cancel_col in cancels.columns:
            cancels["date"] = pd.to_datetime(cancels.get(date_col), errors="coerce")
            cancels["canceldate"] = pd.to_datetime(cancels.get(cancel_col), errors="coerce")
            if cancels["date"].dt.tz is not None: cancels["date"] = cancels["date"].dt.tz_localize(None)
            if cancels["canceldate"].dt.tz is not None: cancels["canceldate"] = cancels["canceldate"].dt.tz_localize(None)
            cancels["wait_sec"] = (cancels["canceldate"] - cancels["date"]).dt.total_seconds()
            cancels = cancels[cancels["wait_sec"] <= 9000]
    else:
        cancels = pd.DataFrame(columns=["userid", "wait_sec", "canceldate", "company"])

    if date_range and len(date_range) == 2 and not cancels.empty:
        cancels = cancels[(cancels["canceldate"] >= start_date) & (cancels["canceldate"] <= end_date)]

    # --- Additional Filters ---
    with st.expander("Additional Filters"):
        tariff_options = sorted(orders.get("tariff", pd.Series(dtype=str)).dropna().astype(str).unique())
        selected_tariffs = st.multiselect("Tariffs", tariff_options)
        profiles_options = sorted(orders.get("profilename", pd.Series(dtype=str)).dropna().astype(str).unique())
        
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            selected_profiles = st.multiselect("Profiles", profiles_options)
            min_distance = st.number_input("Min distance", value=float(orders["distance"].min() if not orders["distance"].dropna().empty else 0))
            min_fare = st.number_input("Min fare", value=float(orders["fare"].min() if not orders["fare"].dropna().empty else 0))
        with filter_col2:
            max_distance = st.number_input("Max distance", value=float(orders["distance"].max() if not orders["distance"].dropna().empty else 100))
            max_fare = st.number_input("Max fare", value=float(orders["fare"].max() if not orders["fare"].dropna().empty else 10000))
        min_cancel_wait = st.number_input("Exclude cancels shorter than (sec)", value=0, step=10)

    # Apply secondary filters
    if selected_tariffs: orders = orders[orders["tariff"].astype(str).isin(selected_tariffs)]
    if selected_profiles: orders = orders[orders["profilename"].astype(str).isin(selected_profiles)]
    if "distance" in orders.columns: orders = orders[(orders["distance"] >= min_distance) & (orders["distance"] <= max_distance)]
    if "fare" in orders.columns: orders = orders[(orders["fare"] >= min_fare) & (orders["fare"] <= max_fare)]
    if min_cancel_wait > 0 and "wait_sec" in cancels.columns: cancels = cancels[cancels["wait_sec"] >= min_cancel_wait]

    grouped_cancels = _group_cancellations(cancels)

    # --- Service Quality Alert Panel ---
    st.markdown("---")
    st.markdown("### 🚨 Service Quality Alert Panel")
    
    alert_cols = st.columns(3)
    with alert_cols[0]:
        min_orders_alert = st.number_input("Min. number of orders", min_value=1, value=10, step=1)
    with alert_cols[1]:
        cancel_rate_alert = st.slider("Cancel Rate Threshold (%)", 0, 100, 15)
    with alert_cols[2]:
        slow_accept_rate_alert = st.slider("Slow Acceptance Threshold (%)", 0, 100, 30)

    # Calculations for the alert panel
    if not orders.empty:
        q3_accept_time = orders["accepted_seconds"].quantile(0.75)
        
        total_orders_co = orders.groupby('company').size().reset_index(name='total_orders')
        slow_accept_co = orders[orders["accepted_seconds"] > q3_accept_time].groupby('company').size().reset_index(name='slow_accept_count')
        cancel_sessions_co = grouped_cancels.groupby('company').size().reset_index(name='cancel_session_count')

        alert_df = pd.merge(total_orders_co, slow_accept_co, on='company', how='left')
        alert_df = pd.merge(alert_df, cancel_sessions_co, on='company', how='left').fillna(0)

        alert_df['cancel_rate'] = (alert_df['cancel_session_count'] / alert_df['total_orders'] * 100)
        alert_df['slow_accept_rate'] = (alert_df['slow_accept_count'] / alert_df['total_orders'] * 100)

        problem_companies = alert_df[
            (alert_df['total_orders'] >= min_orders_alert) &
            (alert_df['cancel_rate'] >= cancel_rate_alert) &
            (alert_df['slow_accept_rate'] >= slow_accept_rate_alert)
        ]

        if not problem_companies.empty:
            st.error(f"Found {len(problem_companies)} companies with potential service quality issues!")
            st.dataframe(problem_companies.style.format({
                'cancel_rate': '{:.1f}%',
                'slow_accept_rate': '{:.1f}%'
            }))
        else:
            st.success("No problem companies found based on the current criteria.")

    # --- Key Metrics Display (RESTORED) ---
    st.markdown("---")
    st.markdown("### Key Metrics")
    stats_excl = {
        "Accepted time (sec)": _calc_stats(orders["accepted_seconds"]),
        "Arrived time (min)": _calc_stats(orders["arrived_minutes"]),
        "Distance (km)": _calc_stats(orders["distance"]),
        "Fare (dram)": _calc_stats(orders["fare"]),
    }
    combined_series = [pd.to_numeric(orders.get("accepted_seconds"), errors="coerce"), pd.to_numeric(grouped_cancels.get("total_wait_sec"), errors="coerce")]
    combined = pd.concat(combined_series, ignore_index=True) if combined_series else pd.Series()
    stats_incl = _calc_stats(combined)
    metrics_df = pd.DataFrame(stats_excl).T
    metrics_df.loc["Accepted time including cancels"] = stats_incl
    
    display_columns = ["Min", "Q1 (25%)", "Median (50%)", "Q3 (75%)", "Max", "IQR", "Average", "Sum", "stDeviation", "Skew"]
    st.dataframe(metrics_df[[col for col in display_columns if col in metrics_df.columns]])
    
    col_a, col_b, col_c = st.columns(3)
    with col_a: st.metric("Total rides", len(orders))
    with col_b: st.metric("Total Cancel Sessions", len(grouped_cancels))
    with col_c: st.metric("Unique users with orders", orders["userid"].nunique())
    
    # --- Analysis of the Slowest 25% of Orders ---
    st.markdown("---")
    st.markdown("### 🕵️ Analysis of the Slowest 25% of Orders")
    q3_arrival_time = orders['arrived_minutes'].quantile(0.75) if not orders.empty else None
    
    min_total_orders = st.number_input("Minimum total orders for analysis", min_value=1, value=5, step=1, help="Only include companies with an order count above this threshold.")

    if q3_arrival_time is not None and not orders.empty:
        slow_orders_df = orders[orders["arrived_minutes"] > q3_arrival_time].copy()
        
        total_orders_by_company = orders.groupby('company').size().reset_index(name='total_orders')
        slow_by_company = slow_orders_df.groupby('company').size().reset_index(name='slow_orders_count')
        
        analysis_df = pd.merge(total_orders_by_company, slow_by_company, on='company', how='left').fillna(0)
        
        analysis_df_filtered = analysis_df[analysis_df['total_orders'] >= min_total_orders].copy()
        
        if not analysis_df_filtered.empty:
            analysis_df_filtered['slow_orders_percent'] = (analysis_df_filtered['slow_orders_count'] / analysis_df_filtered['total_orders'] * 100)
            
            st.info(f"Analysis of companies with **{min_total_orders}** or more orders. Found **{len(slow_orders_df)}** slow orders (longer than {q3_arrival_time:.1f} min).")
            
            st.markdown("##### Slow Order Rate by Company")
            chart_slow_company = alt.Chart(analysis_df_filtered.sort_values('slow_orders_percent', ascending=False).head(15)).mark_bar().encode(
                x=alt.X('slow_orders_percent:Q', title='% of Slow Orders'),
                y=alt.Y('company:N', title='Company', sort='-x'),
                tooltip=['company', 'slow_orders_count', 'total_orders', alt.Tooltip('slow_orders_percent:Q', format='.1f')]
            )
            st.altair_chart(chart_slow_company, use_container_width=True)
            with st.expander("View Analysis Details"):
                st.dataframe(analysis_df_filtered)
        else:
            st.warning(f"No companies with {min_total_orders} or more orders to analyze.")

    # --- Analysis by Hour of Day ---
    st.markdown("---")
    st.markdown("### Analysis by Hour of Day")
    sort_order = list(range(6, 24)) + list(range(0, 6))

    if "orderdate1" in orders.columns:
        st.markdown("#### Orders and Median Arrival Time by Hour")
        orders_by_hour = orders.groupby(orders["orderdate1"].dt.hour).agg(
            order_count=('orderdate1', 'size'),
            median_arrival=('arrived_minutes', 'median')
        ).reset_index().rename(columns={"orderdate1": "hour"})
        
        base = alt.Chart(orders_by_hour).encode(x=alt.X('hour:O', title='Hour of Day', sort=sort_order))
        bar = base.mark_bar().encode(y=alt.Y('order_count:Q', title='Number of Orders'))
        line = base.mark_line(color='red', strokeWidth=3).encode(y=alt.Y('median_arrival:Q', title='Median Arrival (min)'))
        st.altair_chart(alt.layer(bar, line).resolve_scale(y='independent'), use_container_width=True)

    if not grouped_cancels.empty and "session_start_time" in grouped_cancels.columns:
        st.markdown("#### Cancels, Median & Total Wait Time by Hour")
        grouped_cancels['hour'] = pd.to_datetime(grouped_cancels['session_start_time']).dt.hour
        cancels_by_hour = grouped_cancels.groupby('hour').agg(
            cancel_session_count=('hour', 'size'),
            median_wait_sec=('total_wait_sec', 'median'),
            total_wait_min=('total_wait_sec', lambda x: x.sum() / 60)
        ).reset_index()

        base_cancel = alt.Chart(cancels_by_hour).encode(x=alt.X('hour:O', title='Hour of Day', sort=sort_order))
        bar_cancel = base_cancel.mark_bar().encode(y=alt.Y('cancel_session_count:Q', title='Number of Cancel Sessions'))
        line_median = base_cancel.mark_line(color='orange', strokeWidth=3).encode(y=alt.Y('median_wait_sec:Q', title='Median Wait (sec)'))
        line_total = base_cancel.mark_line(color='purple', strokeWidth=3).encode(y=alt.Y('total_wait_min:Q', title='Total Wait (min)'))
        
        st.altair_chart(alt.layer(bar_cancel, line_median, line_total).resolve_scale(y='independent'), use_container_width=True)

    # --- Raw Data Display ---
    st.markdown("---")
    with st.expander("Raw Data History"):
        st.write("Orders History")
        st.dataframe(orders)
        st.write("Grouped Cancellations History (NEW)")
        st.dataframe(grouped_cancels)
        st.write("Original Cancellations History")
        st.dataframe(cancels)
