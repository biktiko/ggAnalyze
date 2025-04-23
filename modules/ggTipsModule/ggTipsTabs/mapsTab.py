# modules/ggTipsModule/ggTipsTabs/mapsTab.py
from __future__ import annotations

import pandas as pd
import folium
from folium.plugins import MarkerCluster, Fullscreen, MiniMap
from streamlit_folium import st_folium
import streamlit as st


# ───────────────────────── helpers ──────────────────────────
def _split_coordinates(coord: str) -> tuple[float | None, float | None]:
    if isinstance(coord, str) and ", " in coord:
        try:
            lat, lon = map(float, coord.split(", "))
            return lat, lon
        except ValueError:
            pass
    return None, None


def _marker_color(days_since_last: int) -> str:
    if days_since_last <= 30:
        return "green"
    if days_since_last <= 90:
        return "orange"
    return "red"


# ───────────────────────── main entry ───────────────────────
def show(data: dict | None = None) -> None:
    st.subheader("Map of Company Locations")

    companies: pd.DataFrame = (data or {}).get("ggtipsCompanies", pd.DataFrame()).copy()
    tips: pd.DataFrame       = (data or {}).get("ggtips", pd.DataFrame()).copy()

    if companies.empty:
        st.info("No company coordinates to plot.")
        return

    need_cols = {"company", "adress", "coordinate"}
    if not need_cols.issubset({c.lower() for c in companies.columns}):
        st.warning(f"Companies must have columns: {need_cols}")
        return

    # ▸ режим карты
    simple_mode = st.checkbox("Simple map", value=False)

    # ▸ транзакционные метрики
    if not tips.empty and "company" in tips.columns:
        stat = (
            tips.groupby("company", observed=True)
                .agg(amount_sum=("amount", "sum"), cnt=("uuid", "count"), last_tx=("date", "max"))
                .reset_index()
        )
    else:
        stat = pd.DataFrame(columns=["company", "amount_sum", "cnt", "last_tx"])

    companies = companies.merge(stat, how="left", on="company")

    first_lat, first_lon = _split_coordinates(companies.iloc[0]["coordinate"])
    if first_lat is None:
        first_lat, first_lon = 40.1792, 44.4991  # fallback — Ереван

    m = folium.Map(location=[first_lat, first_lon], zoom_start=12, tiles="cartodbpositron")

    today = pd.to_datetime("today").normalize()

    # ▸ выбираем контейнер для маркеров
    if simple_mode:
        container = m
        Fullscreen().add_to(m)
    else:
        container = MarkerCluster().add_to(m)
        Fullscreen().add_to(m)
        MiniMap(toggle_display=True, minimized=True).add_to(m)

    # ▸ маркеры
    for _, row in companies.iterrows():
        lat, lon = _split_coordinates(row["coordinate"])
        if lat is None:
            continue

        if pd.notna(row.get("last_tx")):
            days_since = (today - pd.to_datetime(row["last_tx"]).normalize()).days
        else:
            days_since = 10_000

        color = "blue" if simple_mode else _marker_color(days_since)

        popup_html = (
            f"<b>{row['company']}</b><br>{row['adress']}"
            if simple_mode else
            f"""
            <b>{row['company']}</b><br>
            {row['adress']}<br><br>
            <b>Amout:</b> {row.get('amount_sum', 0):,.0f}<br>
            <b>Count:</b> {row.get('cnt', 0)}<br>
            <b>Last tip:</b> {row.get('last_tx', '–')}
            """
        )

        folium.Marker(
            [lat, lon],
            icon=folium.Icon(color=color, icon="info-sign"),
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(container)

    st_folium(m, width=1000, height=650, returned_objects=[])
