# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\modules\ggTipsModule\ggTips_data.py
import pandas as pd
from data_loader import merge_ggtips

def get_combined_tips_data(session_clever_data: dict) -> dict:

    # Initialize lists to collect DataFrames
    combined_data = {
        'ggtips': [],
        'ggtipsCompanies': [],
        'ggtipsPartners': [],
        'ggTeammates': []
    }
    
    for file_data in session_clever_data.values():
        merged_tips = merge_ggtips(file_data['ggtips'])
        # вот он — ваш архив из load_data
        
        archive = file_data.get('partnersArchive', pd.DataFrame())

        if not archive.empty:
            merged_tips = (
                merged_tips
                .merge(
                   archive,
                   on='email', how='left'
                )
            )
        if not merged_tips.empty:
            combined_data['ggtips'].append(merged_tips)
   
    result = {}
    if combined_data['ggtips']:
        result['ggtips'] = pd.concat(combined_data['ggtips'], ignore_index=True)
    else:
        result['ggtips'] = pd.DataFrame()
    
    companies_list = []
    partners_list = []
    teammates_list = []

    for file_data in session_clever_data.values():
        companies = file_data.get('ggtipsCompanies', {}).get('companies')
        if companies is not None and not companies.empty:
            companies_list.append(companies)

        partners = file_data.get('ggtipsPartners', {}).get('partners details')
        if partners is not None and not partners.empty:
            partners_list.append(partners)

        teammates = file_data.get('ggTeammates')
        if teammates is not None and not teammates.empty:
            teammates_list.append(teammates)

    result['ggtipsCompanies'] = pd.concat(companies_list, ignore_index=True) if companies_list else pd.DataFrame()
    result['ggtipsPartners'] = pd.concat(partners_list, ignore_index=True) if partners_list else pd.DataFrame()
    result['ggTeammates'] = pd.concat(teammates_list, ignore_index=True) if teammates_list else pd.DataFrame()

    return result

    
