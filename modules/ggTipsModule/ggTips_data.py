# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\modules\ggTipsModule\ggTips_data.py
import pandas as pd
from data_loader import merge_ggtips

def get_combined_tips_data(session_clever_data: dict) -> dict:
    """
    Из session_clever_data (словарь file_key -> datasets) собирает:
      - все объединённые tips (merge_ggtips + partnersArchive)
      - все ggtipsCompanies['companies']
      - все ggtipsPartners['partners details']
      - все ggTeammates
      - один объединённый defaultInputs (словарь)
    Возвращает dict с DataFrame-ами и defaultInputs.
    """
    # подготовим контейнеры
    combined = {
        'ggtips': [],
        'ggtipsCompanies': [],
        'ggtipsPartners': [],
        'ggTeammates': []
    }
    default_inputs = {}

    for file_data in session_clever_data.values():
        # ——— 1. TIPSES ———
        tips_raw = file_data.get('ggtips', {})          # самый внешний dict
        merged_tips = merge_ggtips(tips_raw)            # ваша внутренняя логика по superadmin/ggpayers/alltips

        # если есть partnersArchive — делаем merge
        archive = file_data.get('partnersArchive', pd.DataFrame())
        if not archive.empty and not merged_tips.empty:
            merged_tips = merged_tips.merge(archive, on='email', how='left')

        if not merged_tips.empty:
            combined['ggtips'].append(merged_tips)

        # ——— 2. COMPANIES ———
        comp = file_data.get('ggtipsCompanies', {}).get('companies', pd.DataFrame())
        if not comp.empty:
            combined['ggtipsCompanies'].append(comp)

        # ——— 3. PARTNERS ———
        part = file_data.get('ggtipsPartners', {}).get('partners details', pd.DataFrame())
        if not part.empty:
            combined['ggtipsPartners'].append(part)

        # ——— 4. TEAMMATES ———
        team = file_data.get('ggTeammates', pd.DataFrame())
        if not team.empty:
            combined['ggTeammates'].append(team)

        # ——— 5. DEFAULT INPUTS ———
        default_inputs.update(file_data.get('defaultInputs', {}))

    # собираем финальный результат
    result = {}
    for key, dfs in combined.items():
        result[key] = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    result['defaultInputs'] = default_inputs

    return result

    
