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
      cómo presentarlos al usuario. Única excepción: `NoMatchingDataError`
      (país sin ningún dato en el rango pedido, no un fallo) se captura en
      `fetch_gas_storage` y se convierte en un DataFrame vacío — es ausencia
      de datos, no una caída de red ni un bug, y así lo distingue el panel.
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

import logging

import pandas as pd
from gie import GiePandasClient
from gie.exceptions import NoMatchingDataError
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
        Índice: fecha (datetime). Vacío (sin columnas) si AGSI+ no tiene ni un
        solo dato para `country` en `[start, end]` — ver `NoMatchingDataError`
        abajo. El panel decide qué mostrar ante un DataFrame vacío.
    """
    if end is None:
        end = pd.Timestamp.today().strftime("%Y-%m-%d")
    try:
        return _client.query_gas_country(country=country, start=start, end=end)
    except NoMatchingDataError:
        # País sin ningún dato en el rango pedido (p.ej. uno sin almacenamiento
        # activo, o fuera de la cobertura real de AGSI+ pese a estar en el
        # enum de la librería). No es un fallo de red ni de la API: es
        # ausencia de datos, y el panel ya sabe leer un DataFrame vacío
        # (ver `panel_reservas_eu_gas`, `if df_limpio.empty`). Cualquier otra
        # excepción (timeout, red, autenticación) se deja propagar tal cual.
        #
        # El índice tiene que ser un DatetimeIndex vacío, no el RangeIndex
        # por defecto de `pd.DataFrame()`: `transform_gas` hace
        # `df.index.year` incondicionalmente, y eso revienta con
        # `AttributeError` sobre un RangeIndex — cambiaría un traceback por
        # otro en vez de evitarlo. Mismo nombre de índice que devuelve
        # `query_gas_country` en el caso real (gasDayStart), por consistencia.
        logging.warning(
            "[gie/gas_storage] %s: sin datos en AGSI+ para %s..%s (NoMatchingDataError)",
            country, start, end,
        )
        return pd.DataFrame(index=pd.DatetimeIndex([], name="gasDayStart"))

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
