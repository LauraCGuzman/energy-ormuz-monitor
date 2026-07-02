"""
Cliente para datos de Eurostat (sin API key — datos públicos).

Usa la librería `eurostat` que accede a la SDMX REST API de Eurostat.

Datasets utilizados:
    - nrg_stk_oem  : reservas de emergencia de petróleo en días de autonomía (NR)
    - nrg_ti_gasm  : origen del gas natural importado por país (TJ_GCV)
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



