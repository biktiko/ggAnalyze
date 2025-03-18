# data_loader.py
import os
import pandas as pd
import numpy as np
import logging

# Настройка логирования для отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Список целевых листов (в нижнем регистре)
TARGET_SHEETS = {"alltips", "ggpayers", "superadmin"}

def normalize_column(col_name: str) -> str:
    """Приводит имя столбца к стандартному виду."""
    return col_name.lower().strip().replace(" ", "").replace("-", "").replace("_", "")

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
        elif norm in {"company", "companyname"}:
            new_cols[col] = "company"
        elif norm in {"partner", "name", "partnername"}:
            new_cols[col] = "partner"
        elif norm in {"region"}:
            new_cols[col] = "region"
        else:
            new_cols[col] = norm
    df.rename(columns=new_cols, inplace=True)
    return df

def load_data_from_file(file_path: str) -> dict:
    """Загружает данные из файла Excel и возвращает словарь с DataFrame для каждого листа."""
    logger.info(f"Loading file: {file_path}")
    data = {key: pd.DataFrame() for key in TARGET_SHEETS}
    if not os.path.exists(file_path):
        logger.error(f"File {file_path} does not exist.")
        return data
    if file_path.lower().endswith(".xlsx"):
        xls = pd.ExcelFile(file_path)
        for sheet in xls.sheet_names:
            sheet_lower = sheet.lower()
            if sheet_lower in TARGET_SHEETS:
                df = pd.read_excel(xls, sheet_name=sheet)
                logger.info(f"Loaded sheet {sheet_lower} with columns: {df.columns.tolist()}")
                df = standardize_columns(df)

                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"], format='%d.%m.%Y %H:%M:%S', errors='coerce')
                    mask = df["date"].isna()
                    df.loc[mask, "date"] = pd.to_datetime(df.loc[mask, "date"], format='%Y-%m-%d %H:%M:%S', errors='coerce')
                    if df["date"].isna().any():
                        logger.warning(f"Some dates in sheet {sheet} could not be parsed:")
                        logger.warning(df[df["date"].isna()][["date"]])

                if "uuid" in df.columns:
                    df.set_index("uuid", inplace=True)
                else:
                    logger.warning(f"Column 'uuid' not found in sheet {sheet}.")
                data[sheet_lower] = df
    else:
        logger.error("Only Excel (.xlsx) files are supported.")
    return data

def merge_sheets(data_dict: dict) -> pd.DataFrame:
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