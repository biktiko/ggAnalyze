# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\modules\ggTipsModule\ggTips_navigation.py

import streamlit as st
import pandas as pd
import re
import math
from modules.ggTipsModule import ggTips_data

def group_by_time_interval(df: pd.DataFrame, interval: str, custom_days: int = 10) -> pd.DataFrame:
    """
    Группирует DataFrame df по столбцу 'date' согласно выбранному интервалу.
    Возвращает DataFrame со столбцами: [time_group, Amount, Count].
    Для интервалов, где возможно, time_group приводится к datetime.
    """
    if 'date' not in df.columns or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if interval == 'All':
        return pd.DataFrame()
    df.sort_values('date', inplace=True)
    earliest_date = df['date'].min()

    if interval == 'Week':
        # Получаем дату начала недели (понедельник)
        # df['time_group'] = df['date'].dt.to_period('W-MON').apply(lambda r: r.start_time)

        # Убедимся, что дата без часового пояса (иначе может влиять tz)
        df['date'] = df['date'].dt.tz_localize(None)

        # dayofweek == 0 для понедельника, 1 для вторника и т.д.
        # Если день недели == 2 (среда), то вычитаем 2 дня, получаем понедельник
        df['time_group'] = df['date'] - pd.to_timedelta(df['date'].dt.dayofweek, unit='D')

        # Нормализуем (обнуляем время), чтобы был 00:00
        df['time_group'] = df['time_group'].dt.normalize()

    elif interval == 'Week partial':
        df['time_group'] = "Week " + (1 + (df['date'].dt.day - 1) // 7).astype(str)

    elif interval == 'Month':
        # Получаем дату первого числа месяца
        df['time_group'] = df['date'].dt.to_period('M').apply(lambda r: r.start_time)
    elif interval == 'Month partial':
        # Вычисляем смещение в месяцах от earliest_date и прибавляем это смещение к earliest_date
        df['month_offset'] = (df['date'].dt.year - earliest_date.year) * 12 + (df['date'].dt.month - earliest_date.month)
        df['time_group'] = df['month_offset'].apply(lambda x: (earliest_date.replace(day=1) + pd.DateOffset(months=x)))
    elif interval == 'Day':
        # Обнуляем время – оставляем только дату
        df['time_group'] = df['date'].dt.normalize()
    elif interval == 'Day partial':
        # Возвращаем дату, полученную прибавлением количества дней от earliest_date
        df['day_offset'] = (df['date'] - earliest_date).dt.days
        df['time_group'] = df['day_offset'].apply(lambda x: earliest_date + pd.Timedelta(days=x))
    elif interval == 'Year':
        # Возвращаем дату 1 января соответствующего года
        df['time_group'] = pd.to_datetime(df['date'].dt.year.astype(str) + '-01-01')
    elif interval == 'Hour':
        # Округляем до начала часа
        df['time_group'] = df['date'].dt.floor('H')
    elif interval == 'Week day':
        # Можно вернуть название дня недели
        df['time_group'] = df['date'].dt.day_name()
    elif interval == 'Custom day':
        # Группируем по интервалам длиной custom_days, возвращая дату начала каждого интервала
        df['days_offset'] = (df['date'] - earliest_date).dt.days
        df['interval_bin'] = df['days_offset'] // custom_days
        df['time_group'] = df['interval_bin'].apply(lambda x: earliest_date + pd.Timedelta(days=x * custom_days))
    else:
        return pd.DataFrame()
    
    grouped = df.groupby('time_group').agg({
        'amount': 'sum',
        'uuid': 'count'
    }).rename(columns={'amount': 'Amount', 'uuid': 'Count'}).reset_index()
    return grouped

def unify_company_name(name: str) -> str:
    """
    Приводит названия компаний из транзакций к единому виду.
    Пример:
      'Karas Tumanyan', 'Karas Tsaghkadzor', 'Karas mashtoc' -> 'Karas'
      'Tashir Teryan', 'Tashir Vanadzor' -> 'Tashir Pizza'
    """
    if not isinstance(name, str):
        return name
    lower = name.lower().strip()
    if lower.startswith('karas'):
        return 'Karas'
    elif lower.startswith('tashir'):
        return 'Tashir Pizza'
    return name

def extract_street_name(full_address: str) -> str:
    """
    Удаляет номер дома и дроби из адреса, оставляя только название улицы.
    Пример: '39/12 Մесրոպ Մաշտոց' -> 'Մесրոպ Մաշտոց'
    """
    if not isinstance(full_address, str):
        return full_address
    return re.sub(r'^\d+(?:/\d+)?\s*', '', full_address).strip()

def show_ggtips_sidebar_filters(data: dict):
    """
    Рисует набор фильтров для транзакций (tips), объединяет их с данными компаний,
    добавляя фильтры по компаниям, региону и улице.
    Фильтр компаний оставлен в одной строке (в будущем можно добавить фильтр по партнёрам).
    
    Возвращает словарь:
      {
        'ggtips': отфильтрованный DataFrame,
        'ggtipsGrouped': сгруппированный DataFrame (по timeInterval),
        'ggtipsCompanies': исходная таблица компаний,
        'ggtipsPartners': исходная таблица партнёров
      }
    """
    # 1. Получаем объединённые данные из модуля ggTips_data
    data = ggTips_data.get_combined_tips_data(data)
    tips = data.get('ggtips', pd.DataFrame())
    companies = data.get('ggtipsCompanies', pd.DataFrame())
    partners = data.get('ggtipsPartners', pd.DataFrame())
    defaultInputs = data.get('defaultInputs', {})
    ggTeammates = data.get('ggTeammates', pd.DataFrame())

    for setting in defaultInputs.keys():
        if setting not in st.session_state:
            st.session_state[setting] = defaultInputs[setting]
    if tips.empty:
        return {
            'ggtips': pd.DataFrame(),
            'ggtipsGrouped': pd.DataFrame(),
            'ggtipsCompanies': companies,
            'ggtipsPartners': partners
        }
    
    # 2. Подготавливаем данные компаний: добавляем company_unified и street_name
    if not companies.empty:
        if 'company' in companies.columns:
            companies['company_unified'] = companies['company']
        else:
            companies['company_unified'] = None
        if 'adress' in companies.columns:
            companies['street_name'] = companies['adress'].apply(extract_street_name)
        else:
            companies['street_name'] = None

    # 3. Обрабатываем таблицу транзакций: добавляем company_unified
    filteredTips = tips.copy()
    if 'company' in filteredTips.columns:
        filteredTips['company_unified'] = filteredTips['company'].apply(unify_company_name)
    else:
        filteredTips['company_unified'] = None

    # 4. Объединяем транзакции с данными компаний по company (left join)
    invalid_values = [None, "", "-", "nan", "null", "undefined", "N/A", "none", "not found"]

    if 'company_x' in filteredTips.columns and 'company_y' in filteredTips.columns:
        filteredTips = (
            filteredTips
            .assign(
                company=lambda df: (
                    df["company_x"].replace(invalid_values, pd.NA)
                    .combine_first(df["company_y"].replace(invalid_values, pd.NA))
                )
            )
            .drop(columns=["company_x", "company_y", "company_unified"], errors="ignore")
        )

    if not companies.empty and "company" in companies.columns and "company" in filteredTips.columns:
        companies_for_join = companies.set_index("company")
        
        filteredTips = filteredTips.drop_duplicates(subset="uuid")  # не забудь сохранить результат!
        
        mergedTips = filteredTips.join(
            companies_for_join,
            on="company",
            how="left",
            rsuffix="_co"
        )
    else:
        mergedTips = filteredTips.copy()

    # 5. Готовим списки для фильтров
    company_values = list(mergedTips['company'].dropna().unique()) if 'company' in mergedTips.columns else []
    region_values = list(mergedTips['region'].dropna().unique()) if 'region' in mergedTips.columns else []
    street_values = list(mergedTips['street_name'].dropna().unique()) if 'street_name' in mergedTips.columns else []

    # Фильтры по start и end (если это datetime)
    start_min, start_max = None, None
    if 'start' in mergedTips.columns and pd.api.types.is_datetime64_any_dtype(mergedTips['start']):
        start_min = mergedTips['start'].min()
        start_max = mergedTips['start'].max()
    end_min, end_max = None, None
    if 'end' in mergedTips.columns and pd.api.types.is_datetime64_any_dtype(mergedTips['end']):
        end_min = mergedTips['end'].min()
        end_max = mergedTips['end'].max()
        
    # 6. Список интервалов для группировки
    timeIntervalOptions = [
        'Week', 
        'Week partial',
        'Month', 'Month partial',
        'Year',
        'Week day',
        'Day', 'Day partial',
        'Hour',
        'Custom day',
        'All'
    ]

    with st.expander('ggTips filters', expanded=True):
        # --- Фильтры транзакций ---
        st.subheader('Transactions filters')
        status_options = list(mergedTips['status'].dropna().unique()) if 'status' in mergedTips.columns else []
        if 'finished' in status_options:
            st.multiselect('Status', status_options, key='Status', default='finished')
        else:
            st.multiselect('Status', status_options, key='Status')

        col1, col2 = st.columns(2)
        with col1:
            ggPayeersOptions = ['Without gg teammates', 'All', 'Only gg teammates']
            if st.session_state.get('ggPayeers') not in ggPayeersOptions:
                st.session_state['ggPayeers'] = 'Without gg teammates'
            st.selectbox('ggPayeers', ggPayeersOptions, key='ggPayeers')

            st.number_input('Min amount', value=st.session_state.get('amountFilterMin', 110),
                            step=1000, min_value=0, max_value=50000, key='amountFilterMin')
            
            date_range = st.date_input("Select date range", [], key='dateRange')

        with col2:
            paymentProcessorOptions = list(mergedTips['payment processor'].dropna().unique()) if 'payment processor' in mergedTips.columns else []
            st.multiselect('Payment Processor', paymentProcessorOptions, key='paymentProcessor')
            st.number_input('Max amount', value=st.session_state.get('amountFilterMax', 50000),
                            step=1000, min_value=0, max_value=50000, key='amountFilterMax')
            
            if 'timeInterval' not in st.session_state:
                st.session_state['timeInterval'] = 'Week'
            interval = st.selectbox('Time interval', timeIntervalOptions, key='timeInterval')

            if st.session_state.get('timeInterval') == 'Custom day':
                st.session_state.setdefault('customInterval', 10)
                st.number_input('Custom days interval', value=st.session_state['customInterval'],
                                step=1, min_value=1, key='customInterval')
                
        # Применяем старые фильтры к mergedTips
        if date_range and len(date_range) == 2 and 'date' in mergedTips.columns:
            s_date, e_date = date_range
            mergedTips = mergedTips[(mergedTips['date'] >= pd.to_datetime(s_date)) &
                                    (mergedTips['date'] <= pd.to_datetime(e_date))]
            
        st.divider()
        st.subheader("Companies filters") 

        # --- Новый блок фильтров (для компаний)  ---

        selected_companies = st.multiselect("Companies", company_values, key="companyFilter")

        if selected_companies:
            mergedTips = mergedTips[mergedTips['company'].isin(selected_companies)]

        colA, colB = st.columns(2)

        with colA:
            selected_regions = st.multiselect("Region", region_values, key="regionFilter")
        with colB:
            selected_streets = st.multiselect("Street Name", street_values, key="streetNameFilter")

        isCompanyWorking = st.selectbox(
            'Is company working?', ['Yes', 'No', "All"], key='isCompanyWorking'
        )

        # Инициализация переменных
        chosen_start_range = []
        chosen_end_range = []

        # Фильтрация компаний и отображение фильтров по дате
        if isCompanyWorking == 'Yes' and 'working status' in companies.columns:
                companies = companies[companies['working status'] == 'true']
                if start_min is not None and start_max is not None:
                    chosen_start_range = st.date_input("Start date range", [], key="startDateRange")
                
        elif isCompanyWorking == 'No':
            companies = companies[companies['working status'] == 'false']
            if end_min is not None and end_max is not None:
                col1, col2 = st.columns(2)
                with col1:
                    chosen_start_range = st.date_input("Start date range", [], key="startDateRange")
                with col2:
                    chosen_end_range = st.date_input("End date range", [], key="endDateRange")

        if chosen_start_range and len(chosen_start_range) == 2 and 'start' in mergedTips.columns:
            s_from, s_to = chosen_start_range
            mergedTips = mergedTips[(mergedTips['start'] >= pd.to_datetime(s_from)) &
                                    (mergedTips['start'] <= pd.to_datetime(s_to))]
            
            companies = companies[(companies['start'] >= pd.to_datetime(s_from)) &
                                    (companies['start'] <= pd.to_datetime(s_to))]

        if 'chosen_end_range' in locals() and chosen_end_range and len(chosen_end_range) == 2 and 'end' in mergedTips.columns:
            e_from, e_to = chosen_end_range
            mergedTips = mergedTips[(mergedTips['end'] >= pd.to_datetime(e_from)) &
                                    (mergedTips['end'] <= pd.to_datetime(e_to))]
            
            companies = companies[(companies['end'] >= pd.to_datetime(e_from)) &
                                    (companies['end'] <= pd.to_datetime(e_to))]
        
        #  Применяем старые фильтры
        if 'amount' in mergedTips.columns:
            mergedTips = mergedTips[(mergedTips['amount'] >= st.session_state['amountFilterMin']) &
                                    (mergedTips['amount'] <= st.session_state['amountFilterMax'])]
        if st.session_state.get('paymentProcessor') and 'payment processor' in mergedTips.columns:
            mergedTips = mergedTips[mergedTips['payment processor'].isin(st.session_state['paymentProcessor'])]
        if st.session_state.get('Status') and 'status' in mergedTips.columns:
            mergedTips = mergedTips[mergedTips['status'].isin(st.session_state['Status'])]
        if st.session_state.get('ggPayeers') == 'Without gg teammates':
            pass
        elif st.session_state.get('ggPayeers') == 'Only gg teammates':
            pass
        # 8. Применяем новые фильтры
        if selected_companies:
            partners = partners[partners['company'].isin(selected_companies)]

        if selected_regions and 'region' in mergedTips.columns:
            mergedTips = mergedTips[mergedTips['region'].isin(selected_regions)]
        if selected_streets and 'street_name' in mergedTips.columns:
            mergedTips = mergedTips[mergedTips['street_name'].isin(selected_streets)]

        mergedTips = mergedTips.drop_duplicates(subset=['uuid'])

        # 1) Метрики по компаниям
        mergedTips = mergedTips.drop_duplicates(subset=['uuid'])
        if 'company' in mergedTips.columns:
            metrics = (
                mergedTips
                .groupby("company", observed=True)
                .agg(
                    Amount = ("amount", "sum"),
                    Count  = ("uuid",   "count"),
                    LastTx = ("date",   "max"),
                )
                .reset_index()
            )
        else:
            metrics = pd.DataFrame(columns=["company", "Amount", "Count", "LastTx"])

        # 2) Метрики по партнёрам
        if "partner" in mergedTips.columns:
            metricsPartners = (
                mergedTips
                .groupby("partner", observed=True)
                .agg(
                    Amount = ("amount", "sum"),
                    Count  = ("uuid",   "count"),
                    LastTx = ("date",   "max"),
                )
                .reset_index()
            )
        else:
            metricsPartners = pd.DataFrame(columns=["partner","Amount","Count","LastTx"])

        # 3) Определяем диапазоны для фильтров
        amt_min, amt_max = 0, math.ceil(metrics.Amount.max() if not metrics.empty else 0)
        cnt_min, cnt_max = 0, math.ceil(metrics.Count.max()  if not metrics.empty else 0)
        date_min = metrics.LastTx.min().date() if not metrics.LastTx.isna().all() else None
        date_max = metrics.LastTx.max().date() if not metrics.LastTx.isna().all() else None

        st.markdown("**By company’s performance:**")
        colA, colB = st.columns(2)
        with colA:
            amt_min_input = st.number_input(
                "Min Amount",
                min_value=amt_min, max_value=amt_max,
                value=amt_min, step=1,
                key="company_amount_min"
            )
        with colB:
            amt_max_input = st.number_input(
                "Max Amount",
                min_value=amt_min, max_value=amt_max,
                value=amt_max, step=1,
                key="company_amount_max"
            )

        colC, colD = st.columns(2)
        with colC:
            cnt_min_input = st.number_input(
                "Min Count",
                min_value=cnt_min, max_value=cnt_max,
                value=cnt_min, step=1,
                key="company_count_min"
            )
        with colD:
            cnt_max_input = st.number_input(
                "Max Count",
                min_value=cnt_min, max_value=cnt_max,
                value=cnt_max, step=1,
                key="company_count_max"
            )

        last_tx_range = st.date_input(
            "Last tip",
            value=[date_min, date_max] if date_min and date_max else [],
            key="company_last_tx_range"
        )

        # 4) Проверяем, тронул ли пользователь фильтры
        filters_changed = not (
            amt_min_input == amt_min and
            amt_max_input == amt_max and
            cnt_min_input == cnt_min and
            cnt_max_input == cnt_max and
            (not last_tx_range or (last_tx_range[0] == date_min and last_tx_range[1] == date_max))
        )

        if filters_changed:
            # 5) Фильтрация компаний
            m = metrics.copy()
            m = m[
                (m.Amount.between(amt_min_input, amt_max_input)) &
                (m.Count.between(cnt_min_input, cnt_max_input))
            ]
            if len(last_tx_range) == 2:
                s_d, e_d = last_tx_range
                m = m[(m.LastTx.dt.date >= s_d) & (m.LastTx.dt.date <= e_d)]
            valid_companies = m["company"].tolist()

            # 6) Фильтрация партнёров
            if not metricsPartners.empty:
                p = metricsPartners.copy()
                p = p[
                    (p.Amount.between(amt_min_input, amt_max_input)) &
                    (p.Count.between(cnt_min_input, cnt_max_input))
                ]
                if len(last_tx_range) == 2:
                    s_d, e_d = last_tx_range
                    p = p[(p.LastTx.dt.date >= s_d) & (p.LastTx.dt.date <= e_d)]
                valid_partners = p["partner"].tolist()
            else:
                valid_partners = []
        else:
            # оставляем всё без фильтрации
            valid_companies = metrics["company"].tolist() if "company" in metrics.columns else []
            valid_partners  = metricsPartners["partner"].tolist() if not metricsPartners.empty and "partner" in metricsPartners.columns else []

        # 7) Применяем фильтр
        if 'company' in mergedTips.columns:
            mergedTips = mergedTips[mergedTips["company"].isin(valid_companies)]
        if 'company' in companies.columns:
            companies  = companies[companies["company"].isin(valid_companies)]

        partners = data.get('ggtipsPartners', pd.DataFrame()).copy()
        if valid_partners and "partner" in partners.columns:
            partners = partners[partners["partner"].isin(valid_partners)]

        # … дальше идёт код отрисовки навигации …


        # 8) Фильтры по партнёрам        
        # Унифицируем название компании в партнёрах (аналогично транзакциям)
        if not partners.empty and 'company' in partners.columns:
            partners['company_unified'] = partners['company'].apply(unify_company_name)
        else:
            partners['company_unified'] = None

        # Готовим список партнёров (приводим к нижнему регистру для удобства)

        # valid_company_names = companies['helpercompanyname'].dropna().unique()
        # partners = partners[partners['company'].isin(valid_company_names)]

        partner_values = []

        if not partners.empty and 'partner' in partners.columns:
            if 'selected_companies' in locals() and selected_companies:
                partners = partners[partners['company'].isin(selected_companies)]

            partners = partners[partners['real?'] == True]

            if st.session_state.get('ggPayeers') == 'Without gg teammates':
                partners['phonenumber'] = partners['phonenumber'].astype('Int64').astype(str).str.strip()
                ggTeammates['NUMBER'] = ggTeammates['number'].astype('Int64').astype(str).str.strip()
                partners = partners[~partners['phonenumber'].isin(ggTeammates['NUMBER'])]
                mergedTips = mergedTips[~mergedTips['payer'].isin(ggTeammates['id'])]

            elif st.session_state.get('ggPayeers') == 'Only gg teammates':
                partners['phonenumber'] = partners['phonenumber'].astype('Int64').astype(str).str.strip()
                ggTeammates['NUMBER'] = ggTeammates['number'].astype('Int64').astype(str).str.strip()
                partners = partners[partners['phonenumber'].isin(ggTeammates['NUMBER'])]

        partner_values = list(partners['partner'].dropna().unique()) if 'partner' in partners.columns else []
        # Раздел Фильтров по партнёрам
        st.divider()
        st.subheader("Partners filters") 

        # Фильтр по avatar – аналогично
        if not partners.empty and 'avatar' in partners.columns:
            partners['avatar'] = partners['avatar'].astype(str).str.lower().str.strip()
            avatar_options = ["true", "false"]
        else:
            avatar_options = []
        
        # Фильтр по partnermessage: создаём столбец, который показывает, есть сообщение или нет
        if not partners.empty and 'partnermessage' in partners.columns:
            partners['msg_exists'] = partners['partnermessage'].apply(
                lambda x: "Exists" if x and str(x).lower() != "nan" and str(x).strip() != "" else "Empty"
            )
            msg_options = ["Exists", "Empty"]
        else:
            msg_options = []
        
        # Фильтр по дате – стандартный диапазон (из столбца date)
        if not partners.empty and 'date' in partners.columns:
            partner_date_min = partners['date'].min()
            partner_date_max = partners['date'].max()
        else:
            partner_date_min, partner_date_max = None, None

        # Фильтр по jsonagg: определим функцию, которая возвращает "Has account", если хотя бы один account непустой, иначе "No account"
        import json
        def has_account(json_str):
            try:
                data_list = json.loads(json_str)
                for item in data_list:
                    if item.get("account") not in (None, "", "null"):
                        return "Has Idram"
                return "No Idram"
            except Exception:
                return "No Idram"
            
        if not partners.empty and 'jsonagg' in partners.columns:
            partners['account_status'] = partners['jsonagg'].apply(has_account)
            account_options = ["Has Idram", "No Idram"]
        else:
            account_options = []
        
        # Новый блок фильтров для partners организуем в 2 столбца
        selected_partner = st.multiselect("Partner", partner_values, key="partnerFilter")
        colP1, colP2 = st.columns(2)
        with colP1:
            selected_avatar = st.multiselect("Avatar", avatar_options, key="partnerAvatarFilter")
            partner_date_range = st.date_input("Partner Date Range", [], key="partnerDateRange")
        with colP2:
            selected_account = st.multiselect("Account Status", account_options, key="partnerAccountFilter")
            selected_msg = st.multiselect("Partner Message", msg_options, key="partnerMsgFilter")
        
        # Применяем фильтры для partners
        partners['partner'] = partners['partner'].astype(str).str.lower().str.strip()
        if selected_partner:
            partners = partners[partners['partner'].isin([p.lower() for p in selected_partner])]
        if selected_avatar:
            partners = partners[partners['avatar'].isin(selected_avatar)]
        if selected_msg:
            partners = partners[partners['msg_exists'].isin(selected_msg)]
        if partner_date_range and len(partner_date_range) == 2 and 'date' in partners.columns:
            pd_from, pd_to = partner_date_range
            partners = partners[(partners['date'] >= pd.to_datetime(pd_from)) &
                                                (partners['date'] <= pd.to_datetime(pd_to))]
        if selected_account:
            partners = partners[partners['account_status'].isin(selected_account)]

        if 'partner' in mergedTips.columns and selected_partner:
            mergedTips['partner'] = mergedTips['partner'].astype(str).str.lower().str.strip()
            mergedTips = mergedTips[mergedTips['partner'].isin(partners['partner'].str.lower())]
    
    # Создаём сгруппированный DataFrame, если выбран интервал группировки
    mergedTips = mergedTips.drop_duplicates(subset=['uuid'])
    groupedTips = pd.DataFrame()
    if st.session_state.get('timeInterval') != 'All':
        if st.session_state.get('timeInterval') == 'Custom day':
            custom_days = st.session_state.get('customInterval', 10)
            groupedTips = group_by_time_interval(mergedTips, st.session_state['timeInterval'], custom_days)
        else:
            groupedTips = group_by_time_interval(mergedTips, st.session_state['timeInterval'])

    mergedTips['region'] = mergedTips['region'].combine_first(mergedTips['region_co'])
    mergedTips = mergedTips.drop(columns=['unnamed: 11', 'unnamed: 12', 'helpercompanyname', 'company_unified_co'], errors='ignore')

    return {
        'ggtips': mergedTips,
        'ggtipsGrouped': groupedTips,
        'ggtipsCompanies': companies,
        'ggtipsPartners': partners,
        'ggTeammates': ggTeammates
    }
