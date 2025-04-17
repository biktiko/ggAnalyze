import streamlit as st

def show(data):

    ggTipsDataFiltered = data['ggtips']
    ggTipsDataGrouped = data['ggtipsGrouped']
    # ggTipsCompaniesData = data['ggtipsCompanies']
    # ggTipsPartnersData = data['ggtipsPartners']

    col1, col2, col3, col4 = st.columns(4)

    avg_amount = ggTipsDataFiltered['amount'].mean()
    max_amount = ggTipsDataFiltered['amount'].max()
    total_count = len(ggTipsDataFiltered)
    total_amount = ggTipsDataFiltered['amount'].sum()

    with col1:
        st.metric("Total Transactions", f"{total_count}")
    with col2:
        st.metric("Total Amount", f"{int(total_amount)}")
    with col3:
        st.metric("One Average Tip", f"{round(avg_amount, 2)}")
    with col4:
        if max_amount>0:
            st.metric("Max Tip", f"{int(max_amount)}")

    # Дополнительные показатели
    min_amount = ggTipsDataFiltered['amount'].min()
    median_amount = ggTipsDataFiltered['amount'].median()
    col5, col6 = st.columns(2)
    with col5:
        if min_amount>0:
            st.metric("Min Tip", f"{int(min_amount)}")
    with col6:
        st.metric("Median Tip", f"{round(median_amount, 2)}")

    # ---------- TIP TIME INTERVAL ----------
    if 'date' in ggTipsDataFiltered.columns and len(ggTipsDataFiltered) >= 2:
        sorted_dates = ggTipsDataFiltered.sort_values('date')['date']
        diffs = sorted_dates.diff().dropna()
        avg_diff = diffs.mean()
        total_seconds = avg_diff.total_seconds()
        if total_seconds < 60:
            tip_interval_str = f"Every {round(total_seconds)} seconds"
        elif total_seconds < 3600:
            minutes = total_seconds / 60
            tip_interval_str = f"Every {round(minutes, 1)} minutes"
        elif total_seconds < 86400:
            hours = total_seconds / 3600
            tip_interval_str = f"Every {round(hours, 1)} hours"
        else:
            days = total_seconds / 86400
            tip_interval_str = f"Every {round(days, 1)} days"
        st.metric("Average Tip Interval", tip_interval_str)
    else:
        st.write("Not enough data to compute tip interval.")

    # ---------- DAILY TIPS STATS ----------
    if 'date' in ggTipsDataFiltered.columns:
        daily = ggTipsDataFiltered.copy()
        daily['day'] = daily['date'].dt.date
        daily_stats = daily.groupby('day').agg({'amount': ['sum', 'count']})
        daily_stats.columns = ['total_amount', 'transaction_count']
        daily_stats = daily_stats.reset_index()
        avg_daily_count = daily_stats['transaction_count'].mean()
        avg_daily_amount = daily_stats['total_amount'].mean()
        col7, col8 = st.columns(2)
        with col7:
            st.metric("Avg Daily Transactions", f"{round(avg_daily_count, 2)}")
        with col8:
            st.metric("Avg Daily Amount", f"{round(avg_daily_amount, 2)}")
        st.subheader("Daily Tips")
        st.dataframe(daily_stats)

    # ---------- TOP 5 BIGGEST TIPS ----------
    top_5_biggest = ggTipsDataFiltered.nlargest(5, 'amount')
    st.subheader("Top 5 Biggest Tips")
    st.table(top_5_biggest[['uuid', 'amount', 'company', 'partner', 'date', 'status']])

    # ---------- TOP 5 PARTNERS & COMPANIES ----------
    if 'partner' in ggTipsDataFiltered.columns:
        top_partners = (
            ggTipsDataFiltered
            .groupby('partner')['amount']
            .sum()
            .nlargest(5)
            .reset_index()
            .rename(columns={'amount':'total_amount'})
        )
        st.subheader("Top 5 Partners by Total Amount")
        st.table(top_partners)
    if 'company' in ggTipsDataFiltered.columns:
        top_companies = (
            ggTipsDataFiltered
            .groupby('company')['amount']
            .sum()
            .nlargest(5)
            .reset_index()
            .rename(columns={'amount':'total_amount'})
        )
        st.subheader("Top 5 Companies by Total Amount")
        st.table(top_companies)

    # ---------- GROUPED STATS ----------
    if not ggTipsDataGrouped.empty:
        st.subheader("Grouped Tips Stats")
        # Таблица "Top 5 intervals by amount" показывает 5 групп (в зависимости от выбранного интервала) с наибольшей суммарной суммой чаевых.
        top_5_intervals = ggTipsDataGrouped.nlargest(5, 'Amount')
        st.write("Top 5 intervals by amount (группа и суммарная сумма):")
        st.table(top_5_intervals)