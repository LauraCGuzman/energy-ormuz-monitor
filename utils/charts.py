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


# Mínimos obligatorios reales por país (Directiva 2009/119/CE).
# Criterio importaciones netas → 90 días (mayoría UE).
# Criterio consumo interno → 61 días (países con producción doméstica significativa).
# España aplica excepción nacional: 92 días por ley propia (CORES).
_MINIMOS_DIAS = {
    'ES': (92, "Mín. legal ES (92 días)"),   # Ley 34/1998 + CORES: 2 días extra
    'DK': (61, "Mín. legal DK (61 días)"),   # Producción Mar del Norte → criterio consumo
    'RO': (61, "Mín. legal RO (61 días)"),   # Yacimientos propios → criterio consumo
    'EE': (61, "Mín. legal EE (61 días)"),   # Oil shale local → criterio consumo
    'HR': (61, "Mín. legal HR (61 días)"),   # Producción e inventario local → criterio consumo
}
_MINIMO_DEFAULT = (90, "Mín. legal UE (90 días)")  # Resto importadores netos


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
    minimo_dias, minimo_label = _MINIMOS_DIAS.get(pais_cod, _MINIMO_DEFAULT)

    fig = px.line(
        d, x='Fecha', y='Dias', markers=True,
        title=f'Reservas de emergencia en días — {nombre}',
        labels={'Dias': 'Días de autonomía', 'Fecha': 'Fecha'}
    )
    fig.add_hline(
        y=minimo_dias, line_dash="dash", line_color="red",
        annotation_text=minimo_label,
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


def plot_lng_utilization(
    df: pd.DataFrame,
    title_zona: str = "UE",
    conflicto: str = "2026-02-28",
):
    """Panel de GNL: ¿siguen llegando barcos, y con cuánto margen?

    Dos filas, porque responden preguntas distintas:
      Fila 1 — inventory/dtmi (%): llenado de los tanques de las terminales.
               Sube SOLO cuando descarga un metanero; baja de forma continua
               por regasificación. De ahí el diente de sierra. La alarma
               temprana no es un nivel: es que los dientes DESAPAREZCAN
               (caída monótona sin recargas = no llegan barcos).
      Fila 2 — sendOut vs dtrs (GWh/d): lo que se inyecta a la red frente al
               máximo técnico. El hueco entre la línea y el techo es la holgura
               (equivale a sendOut/dtrs, pero se ve sin calcular el ratio).

    Decisiones de diseño:
      - NO se aplica media móvil a la fila 1: suavizar borraría los dientes,
        que son justamente la señal.
      - No se mezclan unidades: inventory y dtmi son volumen (10^3 m3 GNL),
        sendOut y dtrs son energía (GWh/d). Cada ratio vive en su fila.
      - coveredCapacity NO se pinta: es metadato (% de instalaciones incluidas
        en la agregación). Se reporta como anotación de calidad, porque una
        caída suya produce un escalón artificial en la serie — un falso positivo.

    Args:
        df: DataFrame indexado por fecha (salida de transform_lng).
        title_zona: nombre legible de la zona para los títulos ("UE", "España").
        conflicto: fecha del marcador vertical de inicio del conflicto.

    Returns:
        plotly.graph_objects.Figure
    """
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    def _col(nombre: str):
        return next((c for c in df.columns if c.lower() == nombre.lower()), None)

    c_inv, c_dtmi = _col("inventory"), _col("dtmi")
    c_so, c_dtrs = _col("sendOut"), _col("dtrs")
    c_cov = _col("coveredCapacity")

    faltan = [n for n, c in [("inventory", c_inv), ("dtmi", c_dtmi), ("sendOut", c_so)] if c is None]
    if faltan:
        raise KeyError(f"Faltan columnas {faltan} en {list(df.columns)}")

    d = pd.DataFrame(index=df.index)
    d["llenado"] = df[c_inv].astype(float) / df[c_dtmi].astype(float).replace(0, np.nan) * 100
    d["sendout"] = df[c_so].astype(float)
    if c_dtrs is not None:
        d["dtrs"] = df[c_dtrs].astype(float).replace(0, np.nan)

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=[
            "<b>¿Están llegando barcos?</b> — GNL en los tanques de las terminales",
            "<b>¿Cuánto se está usando?</b> — envío a la red frente al máximo técnico",
        ],
        vertical_spacing=0.15,
    )

    # ── Subplot 1: llenado de tanques (la alarma) ──
    fig.add_trace(go.Scatter(
        x=d.index, y=d["llenado"],
        name="Tanques llenos (%)",
        mode="lines",
        line=dict(color="#1D3557", width=2),
        hovertemplate="%{y:.1f}%<extra>Tanques llenos</extra>",
    ), row=1, col=1)

    # ── Subplot 2: envío a red + techo de capacidad ──
    if "dtrs" in d:
        fig.add_trace(go.Scatter(
            x=d.index, y=d["dtrs"],
            name="Capacidad máx. de regasificación",
            mode="lines",
            line=dict(color="#A8A8A8", width=1.5, dash="dot"),
            hovertemplate="%{y:,.0f} GWh/d<extra>Máximo técnico</extra>",
        ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=d.index, y=d["sendout"],
        name="Envío a la red",
        mode="lines",
        line=dict(color="#457B9D", width=2),
        fill="tozeroy", fillcolor="rgba(69,123,157,0.15)",
        hovertemplate="%{y:,.0f} GWh/d<extra>Envío a la red</extra>",
    ), row=2, col=1)

    # ── Elementos globales ──
    fig.add_vline(x=conflicto, line_width=1.5, line_dash="dash", line_color="orange",
                  row="all", col="all")
    fig.add_annotation(
        x=conflicto, y=1.02, yref="paper",
        text="Inicio Conflicto (28-Feb)", showarrow=True, arrowhead=1, ax=60, ay=-15,
    )

    fig.update_yaxes(title_text="<b>Tanques llenos</b> (%)", range=[0, 100], row=1, col=1)
    fig.update_yaxes(title_text="<b>Envío a la red</b> (GWh/día)", rangemode="tozero", row=2, col=1)
    fig.update_xaxes(title_text="", row=2, col=1)

    fig.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.10, x=0),
        margin=dict(l=40, r=40, t=80, b=40),
    )

    # ── Calidad del dato (coveredCapacity): anotación, nunca serie ──
    if c_cov is not None:
        cov = df[c_cov].replace(0, np.nan)      # 0 = sin dato, no 0% de cobertura
        if cov.notna().any() and float(cov.min()) < 99.5:
            fig.add_annotation(
                x=0, y=-0.14, xref="paper", yref="paper",
                text=(f"⚠️ Cobertura mínima del agregado: {float(cov.min()):.0f}% "
                      "— hay días con instalaciones ausentes (posible escalón artificial)."),
                showarrow=False, font=dict(size=11, color="#B00020"), xanchor="left",
            )

    return fig