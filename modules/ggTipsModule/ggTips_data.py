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
    
    result['ggtipsCompanies'] = file_data['ggtipsCompanies']['companies'] if file_data['ggtipsCompanies']['companies'] is not None else pd.DataFrame()
    result['ggtipsPartners'] = file_data['ggtipsPartners']['partners details'] if file_data['ggtipsPartners']['partners details'] is not None else pd.DataFrame()
    result['ggTeammates'] = file_data['ggTeammates'] if file_data['ggTeammates'] is not None else pd.DataFrame()

    return result

    
