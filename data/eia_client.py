import re
from urllib.parse import quote, quote_plus

import requests
import pandas as pd
import streamlit as st


_TIMEOUT = (10, 60)  # (conexión, lectura) en segundos


def _redactar(texto, API_KEY):
    """Sustituye la clave por *** en un texto (tal cual, codificada en URL o como api_key=...)."""
    texto = str(texto)
    for variante in {API_KEY, quote(API_KEY, safe=''), quote_plus(API_KEY)}:
        if variante:
            texto = texto.replace(variante, '***')
    return re.sub(r'(api_key=)[^&\s\'")]+', r'\1***', texto)


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
    try:
        respuesta = requests.get(url_base, params=parametros, timeout=_TIMEOUT)
        if respuesta.status_code != 200:
            print(f"❌ Error EIA {series_id}. Status: {respuesta.status_code}")
            print(f"Detalle: {_redactar(respuesta.text[:300], API_KEY)}")
            respuesta.raise_for_status()
    except requests.RequestException as e:
        # Los mensajes de requests/urllib3 incluyen la URL con la query string
        # (api_key=...). Se relanza redactado y `from None` corta la cadena de
        # excepciones, cuya traza volvería a mostrar la URL original.
        mensaje = _redactar(e, API_KEY)
        try:
            nueva = type(e)(mensaje)
        except Exception:
            nueva = requests.RequestException(mensaje)
        raise nueva from None
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


# ── Exportaciones de destilado de EE. UU. (panel diésel EE. UU. → Europa) ─────

_URL_WKLY = "https://api.eia.gov/v2/petroleum/move/wkly/data/"
_URL_EXPC = "https://api.eia.gov/v2/petroleum/move/expc/data/"

# Total de EE. UU. (MBBL, mensual). En `expc` viaja junto a los destinos SOLO como
# referencia del último mes publicado; no es un destino y no entra en ninguna suma.
SERIE_EXPORTS_TOTAL_MENSUAL = 'MDIEXUS1'

SERIE_ES = 'MDIEXSP1'
SERIE_GBR = 'MDIEXUK1'
SERIE_NOR = 'MDIEXNO1'

# Series de `expc` (destino, MBBL) de los 27 Estados miembros de la UE.
# Origen: catálogo de la EIA de `/petroleum/move/expc/` (producto EPD0, proceso EEX,
# unidad MBBL), guardado en exploracion_destilados/raw/
# series_petroleum_move_expc_monthly_product-EPD0_process-EEX.json (Fase 0).
# Selección: los 27 países de la lista oficial de la UE, por nombre de destino
# («U.S. Exports to <país> of Distillate Fuel Oil»), contrastada con el `area-name`
# ISO 3166-1 alfa-3 del catálogo (26 de 27 coinciden; Luxemburgo figura con
# area-name «NA» y solo se identifica por nombre y `duoarea` NUS-NLU). Los IDs no
# son regulares (p. ej. MDIEXBZ1 es Alemania): no se construyen a mano.
# Siete no tienen filas desde 2023 (BG, HR, CZ, EE, LU, MT, SK): su mes ausente
# cuenta como 0 dentro del rango publicado, igual que el resto.
SERIES_UE27 = (
    'MDIEX_NUS-NAU_1',          # Austria
    'MDIEXBE1',                 # Bélgica
    'MDIEX_NUS-NBU_1',          # Bulgaria
    'MDIEX_NUS-NHR_1',          # Croacia
    'MDIEX_NUS-NCY_1',          # Chipre
    'MDIEX_NUS-NCZ_1',          # Chequia
    'MDIEXDA1',                 # Dinamarca
    'MDIEX_NUS-NEN_1',          # Estonia
    'MDIEXFI1',                 # Finlandia
    'MDIEXFR1',                 # Francia
    'MDIEXBZ1',                 # Alemania
    'MDIEXGR1',                 # Grecia
    'MDIEX_NUS-NHU_1',          # Hungría
    'MDIEXEI1',                 # Irlanda
    'MDIEXIT1',                 # Italia
    'M_EPD0_EEX_NUS-NLG_MBBL',  # Letonia
    'M_EPD0_EEX_NUS-NLH_MBBL',  # Lituania
    'MDIEX_NUS-NLU_1',          # Luxemburgo
    'MDIEX_NUS-NMT_1',          # Malta
    'MDIEXNL1',                 # Países Bajos
    'MDIEXPL1',                 # Polonia
    'MDIEXPO1',                 # Portugal
    'MDIEX_NUS-NRO_1',          # Rumanía
    'MDIEX_NUS-NSK_1',          # Eslovaquia
    'MDIEX_NUS-NSI_1',          # Eslovenia
    SERIE_ES,                   # España
    'MDIEXSW1',                 # Suecia
)

# Perímetros del gráfico mensual por destino (D3). España está dentro de UE27 y
# además va aparte; Reino Unido y Noruega quedan fuera del agregado.
PERIMETRO_DESTINOS = {
    'UE27': SERIES_UE27,
    'ES': (SERIE_ES,),
    'GBR': (SERIE_GBR,),
    'NOR': (SERIE_NOR,),
}

_PAGINA_EIA = 5000        # tope duro de filas por petición de la EIA
_MAX_PAGINAS_EIA = 100    # cortafuegos contra un bucle si la API no avanza


def _redactar_excepcion(e, API_KEY):
    """Copia de la excepción de requests con la clave redactada (mismo criterio que `_eia_get`)."""
    mensaje = _redactar(e, API_KEY)
    try:
        return type(e)(mensaje)
    except Exception:
        return requests.RequestException(mensaje)


def _eia_get_paginado(API_KEY, url_base, series_ids, frecuencia, start, longitud=_PAGINA_EIA):
    """Descarga multiserie paginada de la EIA v2 y devuelve DataFrame crudo.

    Regla de la fase: orden estable por (`series`, `period`) — ordenar solo por
    `period` duplica y pierde filas en los empates entre páginas —, recuento igual
    a `response.total` y clave (serie, periodo) única. Si falla cualquiera,
    lanza `RuntimeError` (sin imprimir). Ningún mensaje lleva la clave.
    """
    if not API_KEY:
        raise RuntimeError("Falta EIA_API_KEY")
    series_ids = tuple(series_ids)
    if not series_ids:
        raise ValueError("series_ids vacío")
    filas, total, offset = [], None, 0
    for _ in range(_MAX_PAGINAS_EIA):
        parametros = {
            'api_key': API_KEY,
            'frequency': frecuencia,
            'data[]': 'value',
            'facets[series][]': list(series_ids),
            'start': start,
            'sort[0][column]': 'series',
            'sort[0][direction]': 'asc',
            'sort[1][column]': 'period',
            'sort[1][direction]': 'asc',
            'length': longitud,
            'offset': offset,
        }
        try:
            respuesta = requests.get(url_base, params=parametros, timeout=_TIMEOUT)
            respuesta.raise_for_status()
            resp = respuesta.json()['response']
            total_pagina = int(resp['total'])
            pagina = resp['data']
        except requests.RequestException as e:
            raise _redactar_excepcion(e, API_KEY) from None
        except (KeyError, TypeError, ValueError) as e:
            raise RuntimeError(
                f"Respuesta de la EIA con formato inesperado (offset={offset}): {type(e).__name__}"
            ) from None
        if total is None:
            total = total_pagina
        elif total_pagina != total:
            raise RuntimeError(f"La EIA cambió `total` entre páginas: {total} → {total_pagina}")
        filas.extend(pagina)
        offset += len(pagina)
        if not pagina or offset >= total:
            break
    else:
        raise RuntimeError(f"Más de {_MAX_PAGINAS_EIA} páginas: se aborta")
    if len(filas) != total:
        raise RuntimeError(f"Recuento distinto de `total`: {len(filas)} filas frente a {total}")
    df = pd.DataFrame(filas)
    if not df.empty and df.duplicated(subset=['series', 'period']).any():
        n = int(df.duplicated(subset=['series', 'period']).sum())
        raise RuntimeError(f"Clave (serie, periodo) repetida en {n} filas")
    return df


@st.cache_data(ttl=3600)
def fetch_destilado_exports(API_KEY, frecuencia: str = 'weekly', start: str = '2023-01-01') -> pd.DataFrame:
    """Exportaciones semanales de destilado de EE. UU. (WDIEXUS2), miles de barriles/día."""
    return _eia_get(API_KEY, _URL_WKLY, 'WDIEXUS2', frecuencia, start)


@st.cache_data(ttl=3600)
def fetch_destilado_exports_destino(API_KEY, series_ids: tuple, start: str = '2023-01') -> pd.DataFrame:
    """Exportaciones mensuales de destilado por destino (`expc`, MBBL), en bruto.

    Añade `MDIEXUS1` (total de EE. UU.) a la petición como referencia del último mes
    publicado; el consumidor decide qué filas suma (el total nunca es un destino).
    """
    ids = tuple(dict.fromkeys(tuple(series_ids) + (SERIE_EXPORTS_TOTAL_MENSUAL,)))
    return _eia_get_paginado(API_KEY, _URL_EXPC, ids, 'monthly', start)
