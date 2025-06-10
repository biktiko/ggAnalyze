# C:\Users\user\OneDrive\Desktop\Workspace\ggAnalyze\data_loader.py
import os
import logging
import pandas as pd
import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# Листы, которые мы ожидаем
# ──────────────────────────────────────────────────────────────────────────────
GG_TIPS_SHEETS         = {"alltips", "ggpayers", "superadmin"}
GG_COMPANIES_SHEETS    = {"companies"}
GG_PARTNERS_SHEETS     = {"partners details"}
GG_TEAMMATES_SHEETS    = {"gg teammates", "ggteammates"}
ORDERS_COUNT_SHEETS    = {"orders count"}
clients_SHEETS       = {"clients"}
# New identifiers for serve orders and cancellations
ORDERS_HISTORY_COLUMN = {"acceptedinterval", "accepted_interval"}
CANCELLATIONS_COLUMN  = "canceldate"
# ──────────────────────────────────────────────────────────────────────────────
# Логирование
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Утилиты для нормализации колонок и парсинга дат
# ──────────────────────────────────────────────────────────────────────────────
def normalize_column(col: str) -> str:
    return col.lower().strip().replace("-", "").replace("_", "")

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str)
    mapping = {}
    for col in df.columns:
        norm = normalize_column(col)
        if norm in {"uuid", "remoteorderid"}:
            mapping[col] = "uuid"
        elif norm in {"date", "createdat", "created_at", "transactiondate"}:
            mapping[col] = "date"
        elif norm in {"company", "companyname", "company name"}:
            mapping[col] = "company"
        elif norm in {"partner", "name", "partnername", "partner name"}:
            mapping[col] = "partner"
        elif norm in {"region"}:
            mapping[col] = "region"
        elif norm in {"workingstatus", "working status"}:
            mapping[col] = "working status"
            df[col] = df[col].astype(str).str.lower()
        else:
            mapping[col] = norm
    return df.rename(columns=mapping)

def custom_parse_date(s: str) -> pd.Timestamp:
    try:
        s = s.strip()
        if not s:
            return pd.NaT
        date_part, time_part = [p for p in s.split(" ") if p][:2]
        day, month, year = date_part.split(".")
        hour, minute, second = time_part.split(":")
        return pd.Timestamp(
            int(year), int(month), int(day),
            int(hour), int(minute), int(second)
        )
    except:
        return pd.NaT

def robust_parse_dates(ser: pd.Series, sheet: str) -> pd.Series:
    ser = ser.replace({"nan": None, "NaN": None, "": None})
    if pd.api.types.is_datetime64_any_dtype(ser):
        return ser
    if pd.api.types.is_numeric_dtype(ser):
        return pd.to_datetime(ser, unit="d", origin="1899-12-30", errors="coerce")
    clean = ser.astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    parsed = pd.to_datetime(clean, format="%d.%m.%Y %H:%M:%S",
                            errors="coerce", dayfirst=True)
    mask = parsed.isna()
    if mask.any():
        fb = clean[mask].apply(custom_parse_date)
        still = fb.isna()
        if still.any():
            fb.loc[still] = pd.to_datetime(
                clean[mask][still],
                errors="coerce",
                infer_datetime_format=True,
                dayfirst=True
            )
        parsed.loc[mask] = fb
    return parsed

# ──────────────────────────────────────────────────────────────────────────────
# 1) load_data_from_file
# ──────────────────────────────────────────────────────────────────────────────
def load_data_from_file(path: str) -> dict:

    logger.info(f"Loading file: {path}")
    result = {
        "ggtips": {k: pd.DataFrame() for k in GG_TIPS_SHEETS},
        "ggtipsCompanies": {k: pd.DataFrame() for k in GG_COMPANIES_SHEETS},
        "ggtipsPartners": {k: pd.DataFrame() for k in GG_PARTNERS_SHEETS},
        "ggTeammates": pd.DataFrame(),
        "ordersCount": pd.DataFrame(),
        "clients": pd.DataFrame(),
        # new data types
        "serveOrders": pd.DataFrame(),
        "cancellations": pd.DataFrame(),
    }

    if not os.path.exists(path):
        logger.error(f"File not found: {path}")
        return result

    ext = path.lower().split('.')[-1]
    if ext == "xlsx":
        xls = pd.ExcelFile(path)
        for sheet in xls.sheet_names:
            sl = sheet.lower()
            df = pd.read_excel(xls, sheet_name=sheet)
            df = standardize_columns(df)

            # check for serve orders and cancellation sheets by column names
            cols = set(df.columns.str.lower())
            logger.info(f"Processing sheet: {sheet} (columns: {cols})")
            if ORDERS_HISTORY_COLUMN in cols:
                if "orderdate1" in df.columns:
                    df["orderdate1"] = pd.to_datetime(
                        df["orderdate1"], format="%d/%m/%Y/%H:%M", errors="coerce"
                    )
                result["serveOrders"] = df
                continue
            if CANCELLATIONS_COLUMN in cols:
                if "createdat" in df.columns:
                    df["createdat"] = pd.to_datetime(
                        df["createdat"], format="%d.%m.%Y %H:%M", errors="coerce"
                    )
                if "canceldate" in df.columns:
                    df["canceldate"] = pd.to_datetime(
                        df["canceldate"], format="%d.%m.%Y %H:%M", errors="coerce"
                    )
                result["cancellations"] = df
                continue

            # — ggtips sheets —
            if sl in GG_TIPS_SHEETS:
                if "date" in df.columns:
                    df["date"] = robust_parse_dates(df["date"], sheet)
                if "uuid" in df.columns:
                    df = df.set_index("uuid", drop=False)
                result["ggtips"][sl] = df
                continue

            # — companies —
            if sl in GG_COMPANIES_SHEETS:
                if "date" in df.columns:
                    df["date"] = robust_parse_dates(df["date"], sheet)
                result["ggtipsCompanies"][sl] = df
                continue

            # — partners details —
            if sl in GG_PARTNERS_SHEETS:
                if "date" in df.columns:
                    df["date"] = robust_parse_dates(df["date"], sheet)
                result["ggtipsPartners"][sl] = df
                continue

            # — gg teammates —
            if sl in GG_TEAMMATES_SHEETS:
                result["ggTeammates"] = df
                continue

            # — orders count —
            if sl in ORDERS_COUNT_SHEETS:
                if "date" in df.columns:
                    df["date"] = robust_parse_dates(df["date"], sheet)
                result["ordersCount"] = df
                continue

            # — clients —
            if sl in clients_SHEETS:
                if "date" in df.columns:
                    df["date"] = robust_parse_dates(df["date"], sheet)
                result["clients"] = df
                continue

    elif ext == "csv":
        # если нужен CSV
        df = pd.read_csv(path)
        df = standardize_columns(df)
        if "date" in df.columns:
            df["date"] = robust_parse_dates(df["date"], path)
        # принимаем что это tips
        result["ggtips"] = {"csv": df}

    else:
        logger.error("Unsupported extension: must be .xlsx or .csv")

    return result

# ──────────────────────────────────────────────────────────────────────────────
# 2) Вспомогательные функции для слияния
# ──────────────────────────────────────────────────────────────────────────────
def merge_ggtips(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    order = ["alltips", "ggpayers", "superadmin"]
    dfs = [sheets[k] for k in order if k in sheets and not sheets[k].empty]
    if not dfs:
        return pd.DataFrame()
    # комбинируем с приоритетом
    base = dfs[0].copy()
    for df in dfs[1:]:
        base = base.combine_first(df)
    return base.reset_index(drop=True)

def merge_companies(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    order = ["companies"]
    dfs = [sheets[k] for k in order if k in sheets and not sheets[k].empty]
    if not dfs:
        return pd.DataFrame()
    return dfs[0].reset_index(drop=True)

def merge_partners(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    order = ["partners details"]
    dfs = [sheets[k] for k in order if k in sheets and not sheets[k].empty]
    if not dfs:
        return pd.DataFrame()
    return dfs[0].reset_index(drop=True)

# ──────────────────────────────────────────────────────────────────────────────
# 3) Собираем всё вместе
# ──────────────────────────────────────────────────────────────────────────────
def get_combined_data(session_data) -> dict:
    """
    session_data — это либо 
      1) dict: путь->результат load_data_from_file
      2) list/ndarray: список тех результатов
    Возвращает:
      {
        "ggtips": DataFrame,
        "ggtipsCompanies": DataFrame,
        "ggtipsPartners": DataFrame,
        "ggTeammates": DataFrame,
        "ordersCount": DataFrame
      }
    """
    # приводим к списку
    if isinstance(session_data, dict):
        items = list(session_data.values())
    elif isinstance(session_data, (list, np.ndarray)):
        items = list(session_data)
    else:
        return {}

    # 1) ggtips
    all_tips = []
    for d in items:
        df = merge_ggtips(d.get("ggtips", {}))
        if not df.empty:
            all_tips.append(df)
    combined_tips = pd.concat(all_tips, ignore_index=True) if all_tips else pd.DataFrame()

    # 2) companies
    companies = pd.DataFrame()
    for d in items:
        df = merge_companies(d.get("ggtipsCompanies", {}))
        if not df.empty:
            companies = df
            break

    # 3) partners
    partners = pd.DataFrame()
    for d in items:
        df = merge_partners(d.get("ggtipsPartners", {}))
        if not df.empty:
            partners = df
            break

    # 4) teammates
    teammates = pd.DataFrame()
    for d in items:
        tm = d.get("ggTeammates", pd.DataFrame())
        if not tm.empty:
            teammates = tm
            break

    # 5) ordersCount
    orders = []
    for d in items:
        oc = d.get("ordersCount", pd.DataFrame())
        if not oc.empty:
            orders.append(oc)
    combined_orders = pd.concat(orders, ignore_index=True) if orders else pd.DataFrame()

    # 6) clients
    clients = pd.DataFrame()

    for d in items:
        df = d.get("clients", pd.DataFrame())
        if not df.empty:
            clients = df
            break

    # 7) serve orders
    serve_orders = pd.DataFrame()
    for d in items:
        df = d.get("serveOrders", pd.DataFrame())
        if not df.empty:
            serve_orders = df
            break

    # 8) cancellations
    cancellations = pd.DataFrame()
    for d in items:
        df = d.get("cancellations", pd.DataFrame())
        if not df.empty:
            cancellations = df
            break

    return {
        "ggtips": combined_tips,
        "ggtipsCompanies": companies,
        "ggtipsPartners": partners,
        "ggTeammates": teammates,
        "ordersCount": combined_orders,
        "clients": clients,
        "serveOrders": serve_orders,
        "cancellations": cancellations,
    }
