"""
Cliente para datos de Eurostat (sin API key — datos públicos).

Usa la librería `eurostat` que accede a la SDMX REST API de Eurostat.

Datasets utilizados:
    - nrg_stk_oem  : reservas de emergencia de petróleo en días de autonomía (NR)
    - nrg_stk_oilm : reservas de emergencia de petróleo por producto (THS_T)
    - nrg_ti_gasm  : origen del gas natural importado por país (TJ_GCV)
    - nrg_ti_oilm  : importaciones mensuales de gasóleo (O4671) por origen (THS_T)
"""

import pandas as pd
import eurostat
import streamlit as st


@st.cache_data(ttl=3600)
def fetch_reservas_emergencia() -> pd.DataFrame:
    """Descarga el dataset nrg_stk_oem (reservas de emergencia de petróleo).

    Returns:
        DataFrame crudo tal como lo devuelve la librería eurostat.
        Contiene columnas: freq, stk_flow, unit, geo\\TIME_PERIOD, y columnas de fecha (YYYY-MM).
    """
    return eurostat.get_data_df('nrg_stk_oem',
        filter_pars={'startPeriod': '2022', 'stk_flow': ['STK_EUE_DIR'], 'unit': ['NR']})


@st.cache_data(ttl=3600)
def fetch_stocks_producto() -> pd.DataFrame:
    """Descarga nrg_stk_oilm: reservas de emergencia (STKCL_EUE) por producto, en bruto.

    Crudo, gasolina, jet, gasóleo y fuelóleo (variante bruta de cada `siec`), miles de
    toneladas (THS_T), desde 2022-01. Todos los geo: los 27 miembros hacen falta para
    detectar los huecos que anulan un mes del agregado `EU27_2020`.

    Returns:
        DataFrame crudo de la librería eurostat: columnas freq, stk_flow, siec, unit,
        geo\\TIME_PERIOD y una columna por mes (YYYY-MM).
    """
    return eurostat.get_data_df('nrg_stk_oilm', filter_pars={
        'startPeriod': '2022-01', 'stk_flow': ['STKCL_EUE'], 'unit': ['THS_T'],
        'siec': ['O4100_TOT', 'O4652', 'O4661', 'O4671', 'O4680']})


@st.cache_data(ttl=3600)
def fetch_origen_gas() -> tuple[pd.DataFrame, dict]:
    """Descarga el dataset nrg_ti_gasm (origen del gas importado) y el diccionario de partners.

    Returns:
        Tupla (df, dic_partner) donde:
            df          : DataFrame crudo con columnas freq, siec, partner, unit,
                          geo\\TIME_PERIOD y columnas de fecha (YYYY-MM).
            dic_partner : dict {código_partner: nombre_legible} extraído de Eurostat.
    """
    df = eurostat.get_data_df('nrg_ti_gasm', 
        filter_pars={'startPeriod': '2022', 'siec': ['G3000'], 'unit': ['TJ_GCV']})
    dic_partner = dict(eurostat.get_dic('nrg_ti_gasm', 'partner'))
    dic_partner['Otros proveedores'] = 'Otros proveedores'
    return df, dic_partner


@st.cache_data(ttl=3600)
def fetch_importaciones_gasoleo_us_total() -> pd.DataFrame:
    """Descarga nrg_ti_oilm: importaciones de gasóleo (O4671) de la UE-27 y España, en bruto.

    Partner `US` (Estados Unidos) y `TOTAL` (todas las procedencias), en miles de
    toneladas (THS_T), desde 2023-01. Los vacíos llegan mezclados como NaN y None.

    Returns:
        DataFrame crudo de la librería eurostat: columnas freq, siec, partner,
        unit, geo\\TIME_PERIOD y una columna por mes (YYYY-MM).
    """
    return eurostat.get_data_df('nrg_ti_oilm', filter_pars={
        'startPeriod': '2023-01', 'siec': ['O4671'], 'partner': ['US', 'TOTAL'],
        'geo': ['EU27_2020', 'ES'], 'unit': ['THS_T']})
