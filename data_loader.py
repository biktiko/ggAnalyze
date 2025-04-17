# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\data_loader.py

import os
import pandas as pd
import numpy as np
import logging
import streamlit as st

# Настройка логирования для отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Списки целевых листов (в нижнем регистре)
ggTips_TARGET_SHEETS = {"alltips", "ggpayers", "superadmin"}
ggTipsCompanies_TARGET_SHEETS = {"companies"}
ggTipsPartners_TARGET_SHEETS = {"partners details"}

def normalize_column(col_name: str) -> str:
    """Приводит имя столбца к стандартному виду."""
    return col_name.lower().strip().replace("-", "").replace("_", "")

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Стандартизирует имена столбцов."""
    df.columns = df.columns.astype(str)
    new_cols = {}
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)
        norm = normalize_column(col)
        if norm in {"uuid", "remoteorderid"}:
            new_cols[col] = "uuid"
        elif norm in {"date", "createdat", "created_at", "transactiondate"}:
            new_cols[col] = "date"
        elif norm in {"company", "companyname", "company name"}:
            new_cols[col] = "company"
        elif norm in {"partner", "name", "partnername", "partner name"}:
            new_cols[col] = "partner"
        elif norm in {"region"}:
            new_cols[col] = "region"
        elif norm in {"workingstatus", "working status"}:
            new_cols[col] = "working status"
            df[col] = df[col].astype(str).str.lower()
        else:
            new_cols[col] = norm
    df.rename(columns=new_cols, inplace=True)
    return df

def custom_parse_date(s: str):
    """
    Парсит строку в формате 'DD.MM.YYYY HH:MM:SS' вручную.
    Если не получается, возвращает NaT.
    """
    try:
        # Разбиваем строку на дату и время (удаляем лишние пробелы)
        s = s.strip()
        if not s:
            return pd.NaT
        parts = s.split(' ')
        # Иногда между датой и временем могут быть несколько пробелов, поэтому берем непустые части
        parts = [p for p in parts if p]
        if len(parts) < 2:
            return pd.NaT
        date_part, time_part = parts[0], parts[1]
        day, month, year = date_part.split('.')
        hour, minute, second = time_part.split(':')
        return pd.Timestamp(year=int(year), month=int(month), day=int(day),
                            hour=int(hour), minute=int(minute), second=int(second))
    except Exception as e:
        return pd.NaT

def robust_parse_dates(series: pd.Series, sheet: str) -> pd.Series:
    """
    Надёжно распознаёт даты.
    1. Заменяет "nan", "NaN" и пустые строки на None.
    2. Если серия числовая – предполагает Excel-серийное число.
    3. Если строковая – очищает пробелы, затем пытается явно разобрать формат 'DD.MM.YYYY HH:MM:SS'
       с использованием custom_parse_date. Если не получается – fallback с infer_datetime_format.
    """
    series = series.replace({"nan": None, "NaN": None, "": None})
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_datetime(series, errors='coerce', unit='d', origin='1899-12-30')
    
    # Приводим к строке, убираем лишние пробелы
    series = series.astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
    # Сначала пытаемся явный формат
    parsed = pd.to_datetime(series, format='%d.%m.%Y %H:%M:%S', errors='coerce', dayfirst=True)
    # Если для некоторых значений получилось NaT, применяем custom_parse_date
    mask = parsed.isna()
    if mask.any():
        fallback = series[mask].apply(custom_parse_date)
        # Если и custom_parse_date не смог вернуть дату, попробуем fallback с infer_datetime_format
        still_nan = fallback.isna()
        if still_nan.any():
            fallback.loc[still_nan] = pd.to_datetime(series[mask][still_nan], errors='coerce', infer_datetime_format=True, dayfirst=True)
        parsed.loc[mask] = fallback
    return parsed


def load_data_from_file(file_path: str) -> dict:

    """Загружает данные из файла Excel и возвращает словарь с DataFrame для каждого листа."""
    logger.info(f"Loading file: {file_path}")

    data = {
        'ggtips': pd.DataFrame(),
        'ggtipsCompanies': pd.DataFrame(),
        'ggtipsPartners': pd.DataFrame(),
        'ggTeammates': pd.DataFrame(),
    }

    data['ggtips'] = {key: pd.DataFrame() for key in ggTips_TARGET_SHEETS}
    data['ggtipsCompanies'] = {key: pd.DataFrame() for key in ggTipsCompanies_TARGET_SHEETS}
    data['ggtipsPartners'] = {key: pd.DataFrame() for key in ggTipsPartners_TARGET_SHEETS}

    if not os.path.exists(file_path):
        logger.error(f"File {file_path} does not exist.")
        return data
    
    if file_path.lower().endswith(".xlsx"):
        xls = pd.ExcelFile(file_path)
        for sheet in xls.sheet_names:
            sheet_lower = sheet.lower()
            if sheet_lower in ggTips_TARGET_SHEETS:
                df = pd.read_excel(xls, sheet_name=sheet)
                logger.info(f"Loaded sheet {sheet_lower} with columns: {df.columns.tolist()}")
                df = standardize_columns(df)

                if "date" in df.columns:
                    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
                        df["date"] = robust_parse_dates(df["date"], sheet)
                    if df["date"].isna().any():
                        logger.warning(f"Some dates in sheet {sheet} could not be parsed:")
                        logger.warning(df[df["date"].isna()][["date"]])
                if "uuid" in df.columns:
                    df.set_index("uuid", inplace=True)
                else:
                    logger.warning(f"Column 'uuid' not found in sheet {sheet}.")
                data['ggtips'][sheet_lower] = df

            if sheet_lower in ggTipsCompanies_TARGET_SHEETS:
                df = pd.read_excel(xls, sheet_name=sheet)
                logger.info(f"Loaded sheet {sheet_lower} with columns: {df.columns.tolist()}")
                df = standardize_columns(df)
                if "date" in df.columns:
                    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
                        df["date"] = robust_parse_dates(df["date"], sheet)
                    if df["date"].isna().any():
                        logger.warning(f"Some dates in sheet {sheet} could not be parsed:")
                        logger.warning(df[df["date"].isna()][["date"]])
                data['ggtipsCompanies'][sheet_lower] = df

            if sheet_lower in ggTipsPartners_TARGET_SHEETS:
                df = pd.read_excel(xls, sheet_name=sheet)
                logger.info(f"Loaded sheet {sheet} with columns: {df.columns.tolist()}")
                df = standardize_columns(df)
                if "date" in df.columns:
                    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
                        df["date"] = robust_parse_dates(df["date"], sheet)
                    if df["date"].isna().any():
                        logger.warning(f"Some dates in sheet {sheet} could not be parsed:")
                        logger.warning(df[df["date"].isna()][["date"]])
                data['ggtipsPartners'][sheet_lower] = df
            
            if sheet_lower=='gg teammates' or sheet_lower=='ggteammates':
                df = pd.read_excel(xls, sheet_name=sheet)
                logger.info(f"Loaded sheet {sheet} with columns: {df.columns.tolist()}")
                data['ggTeammates'] = df
    else:
        logger.error("Only Excel (.xlsx) files are supported.")

    return data

def merge_ggTips_sheets(data_dict: dict) -> pd.DataFrame:
    """Объединяет данные из листов по 'uuid' с учетом приоритета."""
    priority_order = ["alltips", "ggpayers", "superadmin"]
    data_dict = {sheet: data_dict[sheet] for sheet in priority_order if sheet in data_dict and not data_dict[sheet].empty}
    if not data_dict:
        logger.warning("No data to merge.")
        return pd.DataFrame()
    
    invalid_values = [None, "N/A", "none", "not found", "", "-", "nan", "null", "undefined"]
    
    for sheet in data_dict:
        if "uuid" not in data_dict[sheet].columns and "uuid" not in data_dict[sheet].index.names:
            logger.error(f"Column 'uuid' missing in sheet {sheet}. Cannot set index.")
            return pd.DataFrame()
        if "uuid" in data_dict[sheet].columns:
            data_dict[sheet].set_index("uuid", inplace=True)
    
    combined_df = data_dict[priority_order[0]].copy()
    
    for col in combined_df.columns:
        if combined_df[col].dtype == 'datetime64[ns]':
            combined_df[col] = combined_df[col].replace({pd.NaT: np.nan})
        else:
            combined_df[col] = combined_df[col].replace(invalid_values, np.nan)
    
    for sheet in priority_order[1:]:
        if sheet in data_dict:
            df = data_dict[sheet].copy()
            for col in df.columns:
                if df[col].dtype == 'datetime64[ns]':
                    df[col] = df[col].replace({pd.NaT: np.nan})
                else:
                    df[col] = df[col].replace(invalid_values, np.nan)
            combined_df = combined_df.combine_first(df)
    
    combined_df.reset_index(inplace=True)
    return combined_df

def merge_ggTipsCompanies_sheets(data_dict: dict) -> pd.DataFrame:
    """Объединяет данные из листов по 'company' с учетом приоритета."""
    priority_order = ["companies", "partners details"]
    data_dict = {sheet: data_dict[sheet] for sheet in priority_order if sheet in data_dict and not data_dict[sheet].empty}
    if not data_dict:
        logger.warning("No data to merge.")
        return pd.DataFrame()
    
    invalid_values = [None, "N/A", "none", "not found", "", "-", "nan", "null", "undefined"]
    
    for sheet in data_dict:
        if "company" not in data_dict[sheet].columns and "company" not in data_dict[sheet].index.names:
            logger.error(f"Column 'Company' missing in sheet {sheet}. Cannot set index.")
            return pd.DataFrame()
        if "company" in data_dict[sheet].columns:
            data_dict[sheet].set_index("company", inplace=True)
    
    combined_df = data_dict[priority_order[0]].copy()
    
    for col in combined_df.columns:
        if combined_df[col].dtype == 'datetime64[ns]':
            combined_df[col] = combined_df[col].replace({pd.NaT: np.nan})
        else:
            combined_df[col] = combined_df[col].replace(invalid_values, np.nan)
    
    for sheet in priority_order[1:]:
        if sheet in data_dict:
            df = data_dict[sheet].copy()
            for col in df.columns:
                if df[col].dtype == 'datetime64[ns]':
                    df[col] = df[col].replace({pd.NaT: np.nan})
                else:
                    df[col] = df[col].replace(invalid_values, np.nan)
            combined_df = combined_df.combine_first(df)
    
    combined_df.reset_index(inplace=True)

    return combined_df
