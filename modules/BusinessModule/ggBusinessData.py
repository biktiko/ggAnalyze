# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\modules\ggTipsModule\ggTips_data.py
import pandas as pd

# def merge_business_data(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
#     sheets = ["orders count"]
#     dfs = [sheets[k] for k in sheets if k in sheets and not sheets[k].empty]
#     if not dfs:
#         return pd.DataFrame()
#     # комбинируем с приоритетом
#     base = dfs[0].copy()
#     for df in dfs[1:]:
#         base = base.combine_first(df)
#     return base.reset_index(drop=True)

def get_combined_business_data(session_clever_data: dict) -> dict:

    # Initialize lists to collect DataFrames
    combined_data = {
        'orders': [],
        'companies': []
    }

    result = {}
    import streamlit as st
    for file_data in session_clever_data.values():
    
        st.write(file_data)
        result['orders'] = file_data['ordersCount'] if file_data['ordersCount'] is not None else pd.DataFrame()
        
        if not result['orders'].empty:
            needed_columns = ['date', 'userid', 'orders']
            result['orders'] = result['orders'][needed_columns]
            combined_data['orders'].append(result['orders'])

        result['companies'] = file_data['statistic'] if file_data['statistic'] is not None else pd.DataFrame()

    if combined_data['orders']:
        result['orders'] = pd.concat(combined_data['orders'], ignore_index=True)
    else:
        result['orders'] = pd.DataFrame()

    return result

    
