"""
Wrapper para el `archive-api` de Open-Meteo (reanálisis ERA5).

Sin clave, sin registro. Se fija `models=era5` explícitamente en vez de dejar
el "best match" por defecto: la validación de la Fase 1 del pliego HDD
(correlación y sesgo país por país frente a Eurostat) se hizo pidiendo
`models=era5`, así que el cliente tiene que pedir exactamente lo mismo que se
validó — el "best match" por defecto mezcla ERA5 con ECMWF IFS en los últimos
días y daría una serie distinta a la que se comprobó en la Fase 1.

Mismo patrón que `portwatch_client.py`: REST público vía `http_get` (timeout y
reintentos comunes), caché de Streamlit, y sin `except`: un fallo de red o un
código de error de la API tienen que propagarse tal cual, igual que en el
resto del repo.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from data.peticiones import http_get

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


@st.cache_data(ttl=86400)
def fetch_daily_temperature(
    lat: float,
    lon: float,
    start: str = "2015-10-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Temperatura media diaria (ERA5) para un punto.

    Args:
        lat: latitud del punto.
        lon: longitud del punto.
        start: fecha de inicio (YYYY-MM-DD).
        end: fecha de fin (None = hasta hoy).

    Returns:
        DataFrame indexado por fecha (datetime), columna `temperatura` (°C).

    Raises:
        requests.HTTPError: si la API devuelve un código de error.
        KeyError: si la respuesta no trae la clave `daily` (formato inesperado).
    """
    if end is None:
        end = pd.Timestamp.today().strftime("%Y-%m-%d")

    respuesta = http_get(
        ARCHIVE_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start,
            "end_date": end,
            "daily": "temperature_2m_mean",
            "models": "era5",
        },
        etiqueta=f"Open-Meteo ({lat}, {lon})",
    )
    respuesta.raise_for_status()
    datos = respuesta.json()

    if "daily" not in datos:
        raise KeyError(f"Respuesta inesperada de Open-Meteo (sin 'daily'): {datos}")

    return pd.DataFrame(
        {"temperatura": datos["daily"]["temperature_2m_mean"]},
        index=pd.to_datetime(datos["daily"]["time"]),
    )
