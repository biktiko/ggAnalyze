# modules/BusinessModule/ggBusinessData.py

import pandas as pd

# def clean_clients(df: pd.DataFrame) -> pd.DataFrame:
#     """
#     Ищет в DataFrame строку-заголовок, где встречаются ключевые поля:
#     userId, company, PhoneNumber, companyManager, Connected Day.
#     Делает её новой шапкой, обрезает всё выше, и оставляет только эти колонки
#     (в правильном регистре).
#     """
#     # если совсем пусто, возвращаем пустушку с нужными именами
#     cols = ["userId","company","PhoneNumber","companyManager","Connected Day"]
#     if df.empty:
#         return pd.DataFrame(columns=cols)

#     # нормализованный набор «ключей»
#     required = {"userid","company","phonenumber","companymanager","connected day"}
#     header_idx = None

#     # ищем строку, где встречается как минимум 3 наших ключа
#     for i, row in df.iterrows():
#         lowered = [str(v).strip().lower() for v in row.values]
#         if sum(1 for v in lowered if v in required) >= 3:
#             header_idx = i
#             break

#     if header_idx is None:
#         # не нашли — возвращаем пустую
#         return pd.DataFrame(columns=cols)

#     # привязываем к каждой колонке её «заголовок» из найденной строки
#     header_row = [str(v).strip().lower() for v in df.loc[header_idx].values]

#     # карта от того, что в header_row, к каноническому названию
#     canon = {
#         "userid":           "userId",
#         "company":          "company",
#         "phonenumber":      "PhoneNumber",
#         "companymanager":   "companyManager",
#         "connected day":    "Connected Day"
#     }

#     # какие колонки действительно нам нужны — их индексы
#     keep = []
#     for idx, h in enumerate(header_row):
#         if h in canon:
#             keep.append((idx, canon[h]))

#     # если вдруг не нашли ни одной — пусто
#     if not keep:
#         return pd.DataFrame(columns=cols)

#     # вырезаем данные начиная со следующей за header_idx строки
#     data = df.iloc[header_idx+1 : , [idx for idx,_ in keep]].copy()
#     # назначаем правильные имена
#     data.columns = [new_name for _, new_name in keep]

#     # сбрасываем индекс, убираем лишние строки
#     return data.reset_index(drop=True)



def get_combined_business_data(session_clever_data: dict) -> dict:
    """
    Собирает из session_clever_data:
      - orders: все листы 'orders count'
      - clients: все листы 'clients' (ключ в load_data_from_file – 'clients')
    """
    orders_list = []
    clients_list  = []
    serve_orders_list = []
    cancellations_list = []
    users_list = []

    for file_data in session_clever_data.values():
        # --- ordersCount ---
        oc = file_data.get("ordersCount", pd.DataFrame())
        if not oc.empty:
            cols = [c for c in ("date","userid","orders") if c in oc.columns]
            orders_list.append(oc[cols].copy())

        # --- clients (обратите внимание на ключ 'clients'!) ---
        st_df = file_data.get("clients", pd.DataFrame())
        if not st_df.empty:
            clients_list.append(st_df.copy())

        # --- serve orders ---
        so = file_data.get("serveOrders", pd.DataFrame())
        if not so.empty:
            serve_orders_list.append(so.copy())

        # --- cancellations ---
        can = file_data.get("cancellations", pd.DataFrame())
        if not can.empty:
            cancellations_list.append(can.copy())

        # --- users mapping ---
        u_df = file_data.get("users", pd.DataFrame())
        if not u_df.empty:
            users_list.append(u_df.copy())

    orders = pd.concat(orders_list, ignore_index=True) if orders_list else pd.DataFrame(columns=["date","userid","orders"])
    clients = pd.concat(clients_list, ignore_index=True) if orders_list else pd.DataFrame()
    serve_orders = pd.concat(serve_orders_list, ignore_index=True) if serve_orders_list else pd.DataFrame()
    cancellations = pd.concat(cancellations_list, ignore_index=True) if cancellations_list else pd.DataFrame()
    users = pd.concat(users_list, ignore_index=True) if users_list else pd.DataFrame()

    return {
        "orders": orders,
        "clients": clients,
        "serveOrders": serve_orders,
        "cancellations": cancellations,
        "users": users,
    }
