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


def plot_reservas_emergencia(
    df_long: pd.DataFrame,
    pais_cod: str,
    nombres_paises: dict,
) -> "plotly.graph_objects.Figure":
    """Línea temporal de reservas de emergencia en días de autonomía para un país UE-27.

    Args:
        df_long: DataFrame con columnas geo, Fecha, Dias (salida de transform_reservas_emergencia).
        pais_cod: código ISO-2 del país seleccionado (ej. 'ES').
        nombres_paises: dict {código: nombre_legible}.

    Returns:
        plotly.graph_objects.Figure
    """
    import plotly.express as px

    d = df_long[df_long['geo'] == pais_cod]
    nombre = nombres_paises.get(pais_cod, pais_cod)

    fig = px.line(
        d, x='Fecha', y='Dias', markers=True,
        title=f'Reservas de emergencia en días — {nombre}',
        labels={'Dias': 'Días de autonomía', 'Fecha': 'Fecha'}
    )
    fig.add_hline(
        y=90, line_dash="dash", line_color="red",
        annotation_text="Mínimo legal (90 días)"
    )
    fig.add_vline(x="2026-02-28", line_dash="dot", line_color="black")
    fig.add_annotation(
        x="2026-02-28", y=1, yref="paper",
        text="Inicio Conflicto (28-Feb)", showarrow=True, arrowhead=1, ax=60, ay=-20
    )
    fig.update_layout(hovermode='x unified', margin=dict(l=40, r=40, t=60, b=40))
    return fig


def plot_origen_gas(
    pivot: pd.DataFrame,
    geo_nombre: str,
    dic_partner: dict,
) -> "plotly.graph_objects.Figure":
    """Área apilada del origen del gas importado para un país o el agregado UE-27.

    Args:
        pivot: DataFrame pivotado (fechas × proveedores), salida de transform_origen_gas.
        geo_nombre: nombre legible del país/agregado para el título.
        dic_partner: dict {código_partner: nombre_legible} de Eurostat.

    Returns:
        plotly.graph_objects.Figure
    """
    import plotly.express as px

    pivot_plot = pivot.rename(columns=dic_partner)

    fig = px.area(
        pivot_plot, x=pivot_plot.index, y=pivot_plot.columns,
        title=f'Origen del gas importado — {geo_nombre} (TJ)',
        labels={'value': 'TJ (GCV)', 'index': 'Fecha', 'variable': 'Proveedor'}
    )
    fig.add_vline(x="2026-02-28", line_dash="dot", line_color="black")
    fig.add_annotation(
        x="2026-02-28", y=1, yref="paper",
        text="Inicio Conflicto (28-Feb)", showarrow=True, arrowhead=1, ax=60, ay=-20
    )
    fig.update_layout(hovermode='x unified', margin=dict(l=40, r=40, t=60, b=40))
    return fig
