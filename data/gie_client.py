"""
Wrapper sobre la librería `gie-py` para consultar AGSI+ y ALSI+.

AGSI+ : reservas de gas subterráneo en Europa (datos diarios desde 2011).
ALSI+ : utilización de terminales LNG en Europa (datos diarios desde 2012).

Ambos endpoints comparten la misma API key, que se obtiene gratis registrándose
en https://agsi.gie.eu.

Decisiones de diseño:
    - Las funciones devuelven `pandas.DataFrame` ya tipados y con índice temporal.
    - El cliente se crea una vez por sesión (cacheable con `st.cache_resource`).
    - Los errores de red o de API se propagan al caller; el dashboard decide
      cómo presentarlos al usuario.
"""
# from gie.agsi_mappings import AGSICountry
# from gie.alsi_mappings import ALSICountry

# Lista de países cubiertos por AGSI+
# (se deriva automáticamente del enum de la librería)
# AGSI_COUNTRIES = [c for c in AGSICountry if c != AGSICountry.EU]
# AGSI_COUNTRIES_EU_AGGREGATE = AGSICountry.EU

# Lista de países cubiertos por ALNG
# LNG_COUNTRIES = [c for c in ALSICountry if c != ALSICountry.EU]
# LNG_COUNTRIES_EU_AGGREGATE = ALSICountry.EU

import pandas as pd
from gie import GiePandasClient
import streamlit as st


@st.cache_resource 

def get_client(api_key: str):
    """Crea un cliente GIE autenticado.

    Args:
        api_key: clave personal de GIE (registro gratuito en agsi.gie.eu).

    Returns:
        Instancia de `GiePandasClient` lista para consultar AGSI+ y ALSI+.
    """
    return GiePandasClient(api_key=api_key)

@st.cache_data(ttl=3600)

def fetch_gas_storage(
    _client,
    country: str = "ES",
    start: str = "2022-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Consulta AGSI+ — nivel de llenado de reservas de gas subterráneo.

    Args:
        client: cliente GIE autenticado.
        country: código ISO-2 del país (por defecto España).
        start: fecha de inicio (YYYY-MM-DD).
        end: fecha de fin (None = hasta hoy).

    Returns:
        DataFrame con columnas: gasInStorage, full (%), trend, injection, withdrawal.
        Índice: fecha (datetime).
    """
    if end is None:
        end = pd.Timestamp.today().strftime("%Y-%m-%d")
    return _client.query_gas_country(country=country, start=start, end=end)

@st.cache_data(ttl=3600)

def fetch_lng(
    _client,
    country: str = "EU",
    start: str = "2022-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Consulta ALSI+ — send-out e inventario de terminales LNG (nivel país/UE).

    A diferencia de AGSI+ (stock subterráneo), ALSI+ mide el pulso de llegada
    de GNL: cuánto gas se regasifica e inyecta a la red cada día. Es el
    indicador adelantado frente al mix de origen de Eurostat (~3 meses de desfase).

    Ojo con dos cosas:
        - El código del agregado europeo en ALSI es "EU" (NO "EU27_2020" como en
          Eurostat, ni "ES").
        - ALSI solo cubre países CON terminal de regasificación
          (BE, HR, FI, FR, DE, GR, IT, LT, NL, PL, PT, ES, GB) + agregado "EU".
          Fíjate: Grecia es "GR" (no "EL") y GB (no-UE) está incluido, así que
          para UE-27 puro usa "EU", que GIE ya agrega por ti.

    Args:
        _client: cliente GIE autenticado (misma key que AGSI+).
        country: código del país o "EU" para el agregado (por defecto UE).
        start: fecha de inicio (YYYY-MM-DD).
        end: fecha de fin (None = hasta hoy).

    Returns:
        DataFrame indexado por fecha. Columna clave: sendOut (GWh/d, el caudal a
        red). También lngInventory (GWh en tanques), full (%), dtmi, trend.
        Nota: gie-py anota el retorno como list[dict], pero el PandasClient
        devuelve un DataFrame con índice temporal, igual que query_gas_country.
    """
    if end is None:
        end = pd.Timestamp.today().strftime("%Y-%m-%d")
    return _client.query_lng_country(country=country, start=start, end=end)


@st.cache_data(ttl=3600)

def fetch_lng_terminal(
    _client,
    terminal: str,
    start: str = "2022-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Consulta ALSI+ a nivel de terminal individual (por puerto).

    Terminales españolas: "bilbao", "barcelona", "cartagena", "huelva",
    "sagunto", "mugardos".

    Args:
        _client: cliente GIE autenticado.
        terminal: identificador de la terminal (enum ALSITerminal de gie-py).
        start: fecha de inicio (YYYY-MM-DD).
        end: fecha de fin (None = hasta hoy).

    Returns:
        DataFrame indexado por fecha con sendOut, lngInventory, full, etc.
    """
    if end is None:
        end = pd.Timestamp.today().strftime("%Y-%m-%d")
    return _client.query_lng_terminal(terminal=terminal, start=start, end=end)
