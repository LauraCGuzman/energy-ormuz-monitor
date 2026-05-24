"""
Funciones de visualización reutilizables (Plotly).

Cada función recibe un DataFrame procesado y devuelve un objeto
`plotly.graph_objects.Figure` para ser renderizado con `st.plotly_chart`.

Principio: las funciones de este módulo no consultan datos ni hacen
cálculos analíticos — solo dibujan. Mantener la separación es lo que
permitirá reutilizar el código en el proyecto estrella (Fase 1 trilogía).
"""

from __future__ import annotations

import pandas as pd


def plot_gas_storage_level(df: pd.DataFrame, title: str = "Nivel de reservas"):
    """Serie temporal del % de llenado de reservas de gas.

    Args:
        df: DataFrame con índice de fecha y columna `full` (porcentaje).
        title: título del gráfico.

    Returns:
        plotly.graph_objects.Figure
    """
    raise NotImplementedError


def plot_lng_utilization(df: pd.DataFrame, title: str = "Utilización terminales LNG"):
    """Utilización de terminales LNG (envíos a red vs capacidad).

    Args:
        df: DataFrame con índice de fecha y columnas `dtmi`, `sendout`.
        title: título del gráfico.

    Returns:
        plotly.graph_objects.Figure
    """
    raise NotImplementedError


def plot_hormuz_traffic(df: pd.DataFrame, title: str = "Tráfico por Hormuz"):
    """Tráfico marítimo por el Estrecho de Hormuz, por tipo de buque.

    Args:
        df: DataFrame con índice de fecha y columnas por tipo de buque.
        title: título del gráfico.

    Returns:
        plotly.graph_objects.Figure
    """
    raise NotImplementedError
