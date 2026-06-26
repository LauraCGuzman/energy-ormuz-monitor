import requests
import pandas as pd
import streamlit as st


def _eia_get(API_KEY, url_base, series_id, frecuencia, start):
    """Helper interno: realiza una petición a la EIA v2 y devuelve DataFrame crudo."""
    if not API_KEY:
        raise RuntimeError("Falta EIA_API_KEY")
    parametros = {
        'api_key': API_KEY,
        'frequency': frecuencia,
        'data[]': 'value',
        'facets[series][]': series_id,
        'start': start,
        'sort[0][column]': 'period',
        'sort[0][direction]': 'asc'
    }
    respuesta = requests.get(url_base, params=parametros)
    if respuesta.status_code != 200:
        print(f"❌ Error EIA {series_id}. Status: {respuesta.status_code}")
        print(f"Detalle: {respuesta.text[:300]}")
        respuesta.raise_for_status()
    datos_json = respuesta.json()
    total_disponible = int(datos_json['response']['total'])
    lista_datos = datos_json['response']['data']
    if len(lista_datos) < total_disponible:
        print(f"⚠️ {series_id} truncado: {len(lista_datos)} de {total_disponible}")
    return pd.DataFrame(lista_datos)


_URL_SPT  = "https://api.eia.gov/v2/petroleum/pri/spt/data/"
_URL_WSTK = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"
_URL_PSUP = "https://api.eia.gov/v2/petroleum/cons/wpsup/data/"


@st.cache_data(ttl=3600)
def fetch_brent_spot(API_KEY, frecuencia: str = 'daily', start: str = '2025-01-01') -> pd.DataFrame:
    return _eia_get(API_KEY, _URL_SPT, 'RBRTE', frecuencia, start)


@st.cache_data(ttl=3600)
def fetch_spr_stocks(API_KEY, frecuencia: str = 'weekly', start: str = '2025-01-01') -> pd.DataFrame:
    """Reservas estratégicas de crudo EEUU — SPR (WCSSTUS1), miles de barriles."""
    return _eia_get(API_KEY, _URL_WSTK, 'WCSSTUS1', frecuencia, start)


@st.cache_data(ttl=3600)
def fetch_comercial_stocks(API_KEY, frecuencia: str = 'weekly', start: str = '2025-01-01') -> pd.DataFrame:
    """Reservas comerciales de crudo EEUU (WCESTUS1), miles de barriles."""
    return _eia_get(API_KEY, _URL_WSTK, 'WCESTUS1', frecuencia, start)


# ── Productos petrolíferos ────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_destilado_stocks(API_KEY, frecuencia: str = 'weekly', start: str = '2023-01-01') -> pd.DataFrame:
    """Existencias semanales de destilado (WDISTUS1), miles de barriles."""
    return _eia_get(API_KEY, _URL_WSTK, 'WDISTUS1', frecuencia, start)


@st.cache_data(ttl=3600)
def fetch_jet_stocks(API_KEY, frecuencia: str = 'weekly', start: str = '2023-01-01') -> pd.DataFrame:
    """Existencias semanales de jet fuel (WKJSTUS1), miles de barriles."""
    return _eia_get(API_KEY, _URL_WSTK, 'WKJSTUS1', frecuencia, start)


@st.cache_data(ttl=3600)
def fetch_destilado_supplied(API_KEY, frecuencia: str = 'weekly', start: str = '2023-01-01') -> pd.DataFrame:
    """Product supplied de destilado (WDIUPUS2), miles de barriles/día — ya es tasa."""
    return _eia_get(API_KEY, _URL_PSUP, 'WDIUPUS2', frecuencia, start)


@st.cache_data(ttl=3600)
def fetch_jet_supplied(API_KEY, frecuencia: str = 'weekly', start: str = '2023-01-01') -> pd.DataFrame:
    """Product supplied de jet (WKJUPUS2), miles de barriles/día — ya es tasa."""
    return _eia_get(API_KEY, _URL_PSUP, 'WKJUPUS2', frecuencia, start)
