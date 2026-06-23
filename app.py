"""
Monitor Energético Europa/Ormuz — Dashboard principal.

Visualiza el estado actual de la seguridad energética europea bajo el
contexto del conflicto del Estrecho de Hormuz (inicio 28-feb-2026):
    - Flujos marítimos por el Estrecho (IMF PortWatch)
    - Precio Brent spot + reservas estratégicas EEUU (EIA)
    - Reservas de gas subterráneo Europa (GIE AGSI+)
    - Reservas de emergencia de petróleo en días por país (Eurostat)
    - Origen del gas importado por país (Eurostat)

Punto de entrada: `streamlit run app.py`
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Imports de extracción y transformación (asumiendo estructura de paquete 'data')
from data.eia_client import fetch_brent_spot, fetch_spr_stocks  
from data.gie_client import get_client, fetch_gas_storage
from data.portwatch_client import fetch_chokepoint_flows
from data.transform import transform_eia, transform_portwatch, transform_gas, transform_reservas_emergencia, transform_origen_gas, NOMBRES_PAISES_UE, NOMBRES_GEO
from data.eurostat_client import fetch_reservas_emergencia, fetch_origen_gas
from utils.charts import plot_reservas_emergencia, plot_origen_gas


# Configuración de la página (debe ser la primera llamada a st)
st.set_page_config(
    page_title="Monitor Energético Ormuz",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

def panel_brent() -> None:
    """Panel autocontenido para la serie temporal del Brent Spot."""
    st.subheader("Evolución de Reservas de Crudo de EEUU vs. Precio del Brent")

    API_KEY = st.secrets['EIA_API_KEY']
    # 1. Extracción (Bruto)
    data_brent_bruto = fetch_brent_spot(API_KEY)
    data_reservas_bruto = fetch_spr_stocks(API_KEY)

    # 2. Transformación (Significado del dato)
    data_brent = transform_eia(data_brent_bruto)
    data_reservas = transform_eia(data_reservas_bruto)

    # 3. Renderizado (Visualización)
    # 1. Crear la figura base con el contenedor para eje secundario
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 2. Añadir la serie de Reservas (Eje Y Primario - Izquierda)
    fig.add_trace(
        go.Scatter(
            x=data_reservas.index,
            y=data_reservas["value"],
            name="Reservas Crudo",
            mode="lines",
            line=dict(color="#1D3557")  # Azul oscuro
        ),
        secondary_y=False
    )

    # 3. Añadir la serie del Brent (Eje Y Secundario - Derecha)
    fig.add_trace(
        go.Scatter(
            x=data_brent.index,
            y=data_brent["value"],
            name="Precio Brent",
            mode="lines",
            line=dict(color="#E63946")  # Rojo para contraste
        ),
        secondary_y=True
    )

    # 4. Configurar títulos, alinear leyenda y hover
    fig.update_layout(
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02, 
            x=0, 
            xanchor="left"
        )
    )

    # Rotular ejes Y (Quitamos el texto del eje X para liberar espacio)
    fig.update_yaxes(title_text="<b>Reservas</b> (Miles de barriles)", secondary_y=False)
    fig.update_yaxes(title_text="<b>Precio Brent</b> (USD/barril)", secondary_y=True)
    fig.update_xaxes(title_text="") # <-- Dejamos esto vacío para eliminar el "Fecha" intrusivo

    # 5. Línea vertical del conflicto (Se mantiene igual)
    fig.add_vline(x="2026-02-28", line_width=2, line_dash="dash", line_color="orange")
    fig.add_annotation(
        x="2026-02-28", y=1, yref="paper",
        text="Inicio Conflicto (28-Feb)", showarrow=True, arrowhead=1, ax=60, ay=-20
    )

    # 6. Límite técnico de las reservas (150.000)
    fig.add_hline(
        y=150000, line_width=1.5, line_dash="dot", line_color="red",
        annotation_text="Límite operativo crítico (150M bbl)",
        annotation_position="top left"
    )

    # 7. Nota al pie reajustada y más baja
    fig.add_annotation(
        x=0,
        y=-0.22,  # <-- Bajada de -0.18 a -0.22 para alejarla bien de los números del eje X
        xref="paper",
        yref="paper",
        text="<i>Nota: El límite de 150M de barriles representa el umbral crítico estimado de seguridad operativa de la Reserva Estratégica de Petróleo (SPR).</i>",
        showarrow=False,
        font=dict(size=11, color="gray"),
        xanchor="left"
    )

    # Aumentamos el colchón inferior a 120 para que quepa la nota reubicada
    fig.update_layout(
        margin=dict(b=120) # <-- De 100 sube a 120
    )

    # Para renderizar en Streamlit: st.plotly_chart(fig, use_container_width=True)
    st.plotly_chart(fig, width='stretch')
        


def panel_reservas_eu() -> None:
    """Panel autocontenido para las reservas de gas subterráneo en España."""
    st.subheader("Reservas de gas en Europa — comparativa por año(AGSI+)")
    
    # Inicialización temporal del cliente GIE (usando variables de entorno locales)

    api_key = st.secrets["GIE_API_KEY"]
    client_gie = get_client(api_key=api_key)
    
    # 1. Extracción (Bruto) - Filtramos por Europa "EU"
    df_bruto = fetch_gas_storage(client_gie, "EU")
    
    # 2. Transformación (Significado del dato)
    df_limpio = transform_gas(df_bruto)
    
    # 3. Renderizado (Visualización)
    # Nota: El índice temporal de GIE es 'gasDayStart'

    # Mostrar el gráfico interactivo
    # 3. Renderizado (Visualización)
    # Mostrar el gráfico interactivo
    fig = px.line(
        df_limpio, 
        x="fecha_normalizada",  # Usamos la nueva columna de fechas alineadas
        y="gasInStorage", 
        color=df_limpio["año"].astype(str),
        labels={
            "gasInStorage": "Gas en Almacenamiento (TWh)", 
            "fecha_normalizada": "Fecha (Día/Mes)", 
            "color": "Año"
        },
        #title="Reservas de gas en Europa — comparativa por año"
    )
    
    # BONUS COSMÉTICO: Ajustar el eje X y el formato del hover
    fig.update_xaxes(
        tickformat="%b",        # Muestra solo el nombre corto del mes (ene, feb, mar...) en el eje
        dtick="M1"             # Fuerza a que haya una marca por cada mes
    )
    
    fig.update_traces(
        # Cambiamos el comportamiento del hover para que muestre el día y mes real,
        # junto con el año real que viene de la leyenda de colores, ocultando el 2024 fantasma.
        hovertemplate="<b>Año %{fullData.name}</b><br>Fecha: %{x|%d-%b}<br>Gas: %{y:.2f} TWh<extra></extra>"
    )
    st.plotly_chart(fig, width='stretch')
        

def panel_portwatch() -> None:
    """Panel estrella: Tránsito de petroleros en el Estrecho de Hormuz."""
    st.subheader("Flujos Marítimos: Estrecho de Hormuz (IMF PortWatch)")
    
    # 1. Extracción (Bruto)
    # El cliente de PortWatch o tu función mapeada para Hormuz
    df_bruto = fetch_chokepoint_flows("chokepoint6", 2025)
    
    # 2. Transformación (limpieza + media móvil 7 días en transform_portwatch)
    df_limpio = transform_portwatch(df_bruto)

    date_max = max(df_limpio.index).strftime("%d-%m-%Y")
    # 4. Renderizado
    # Usamos el índice (date) de forma continua en el eje X
    fig = px.line(
        df_limpio,
        x=df_limpio.index,
        y="n_tanker_smooth",
        labels={
            "date": "Fecha",
            "n_tanker_smooth": "Media Móvil (7 días)"
        },
        title="Tránsito Diario de Petroleros (Tankers) — Línea Temporal Continua",
        color_discrete_sequence=["#E63946"]  # Un color que resalte la criticidad
    )
    
    # Ajustes estéticos para marcar el conflicto
    fig.update_xaxes(
        rangeslider_visible=False,
        title_text="Línea de tiempo"
    )
    fig.update_yaxes(title_text="Número de Petroleros / Día")
    
    # Añadir línea vertical en la fecha del conflicto (28 de febrero de 2026)
    fig.add_vline(
        x="2026-02-28", 
        line_width=2, 
        line_dash="dash", 
        line_color="orange"
    )
    fig.add_annotation(
        x="2026-02-28",
        y=df_limpio["n_tanker_smooth"].max(),
        text="Inicio Conflicto (28-Feb)",
        showarrow=True,
        arrowhead=1,
        ax=60,
        ay=-20
    )

    # Renderizar gráfico
    st.plotly_chart(fig, width='stretch')
    
    # 4.1. Añadir el pie de foto con la fecha máxima y el desfase
    st.caption(f"Datos hasta el {date_max} · Actualización semanal, 2-3 días de desfase")
    
    # 5. CONTEXTO CRÍTICO (Disclaimer AIS — Obligatorio §11)
    st.info(
        "⚠️ **Nota metodológica sobre los datos (Efecto Transpondedor):** "
        "La drástica caída observada en las gráficas refleja los tránsitos detectados mediante el "
        "Sistema de Identificación Automática (AIS). Debido a la intensificación del conflicto, el *jamming*, "
        "el *spoofing* de señales GPS y la decisión estratégica de los capitanes de apagar sus transpondedores "
        "para evitar ser rastreados en zonas de riesgo distorsionan el volumen real. La lectura rigurosa de "
        "este indicador es de **'tránsitos observados vía AIS'**, y no necesariamente una interrupción total del "
        "flujo físico de crudo."
    )


def panel_reservas_emergencia() -> None:
    """Panel interactivo: reservas de emergencia en días por país (UE-27)."""
    st.subheader("Reservas de emergencia de petróleo de la UE-27 (en días de importación/consumo)")

    # 1. Extracción (se descarga una vez y queda cacheado)
    df_crudo = fetch_reservas_emergencia()

    # 2. Transformación
    df_long = transform_reservas_emergencia(df_crudo)

    # 3. Desplegable de país
    codigos_disponibles = sorted(df_long['geo'].unique())
    opciones = sorted(
        [(NOMBRES_PAISES_UE[c], c) for c in codigos_disponibles if c in NOMBRES_PAISES_UE],
        key=lambda x: x[0]
    )
    nombres_display = [nombre for nombre, _ in opciones]
    codigos = [cod for _, cod in opciones]

    idx_es = codigos.index('ES') if 'ES' in codigos else 0
    seleccion = st.selectbox(
        "País:", nombres_display, index=idx_es, key="sel_reservas_emergencia"
    )
    pais_cod = codigos[nombres_display.index(seleccion)]

    # 4. Renderizado
    if df_long[df_long['geo'] == pais_cod].empty:
        st.warning(f"No hay datos para {seleccion}.")
        return

    fig = plot_reservas_emergencia(df_long, pais_cod, NOMBRES_PAISES_UE)
    st.plotly_chart(fig, width='stretch')

    ultima_fecha = df_long['Fecha'].max().strftime("%B %Y")
    st.caption(f"Última actualización de datos: {ultima_fecha} · Fuente: Eurostat (nrg_stk_oem)")
    st.info(
        "**Nota:** Autonomía del stock de emergencia de crudo y productos petrolíferos de los 27 Estados miembros. "
        "Los días expresan el escudo de seguridad individual de cada país frente a su propio consumo e importaciones netas, "
        "tomando como referencia el umbral mínimo de 90 días exigido por la directiva europea. Fuente: Eurostat."
    )


def panel_origen_gas() -> None:
    """Panel interactivo: origen del gas importado por país o agregado UE-27."""
    st.subheader("Origen del gas importado")

    # 1. Extracción (dataset completo + diccionario de partners — cacheado)
    df_gas, dic_partner = fetch_origen_gas()

    # 2. Desplegable: UE primero, luego países alfabético
    codigos_paises = sorted(
        [c for c in NOMBRES_GEO if c != 'EU27_2020'],
        key=lambda c: NOMBRES_GEO[c]
    )
    opciones = [(NOMBRES_GEO['EU27_2020'], 'EU27_2020')] + [
        (NOMBRES_GEO[c], c) for c in codigos_paises
    ]
    nombres_display = [nombre for nombre, _ in opciones]
    codigos = [cod for _, cod in opciones]

    idx_es = codigos.index('ES') if 'ES' in codigos else 0
    seleccion = st.selectbox(
        "País:", nombres_display, index=idx_es, key="sel_origen_gas"
    )
    geo = codigos[nombres_display.index(seleccion)]
    geo_nombre = NOMBRES_GEO.get(geo, geo)

    # 3. Transformación para el país seleccionado
    pivot = transform_origen_gas(df_gas, geo)

    if pivot is None or pivot.empty:
        st.warning(f"No hay datos de origen para {geo_nombre}.")
        return

    # 4. Renderizado
    fig = plot_origen_gas(pivot, geo_nombre, dic_partner)
    st.plotly_chart(fig, width='stretch')

    ultima_fecha = pivot.index.max().strftime("%B %Y")
    st.caption(f"Última actualización de datos: {ultima_fecha} · Fuente: Eurostat (nrg_ti_gasm)")


def main() -> None:
    """Punto de entrada del dashboard."""
    st.title("Monitor Energético Europa/Ormuz")
    st.caption(
        "Datos físicos verificables sobre la situación energética europea "
        "desde el inicio del conflicto del Estrecho de Hormuz (28-feb-2026)."
    )

    # --- PASO 1: El estrecho de Hormuz ---
    panel_portwatch()

    # --- PASO 2: Brent+ reservas petróleo de EEUU ---
    panel_brent()
    
    # --- PASO 3: Reservas de gas EU ---
    panel_reservas_eu()

    # --- PASO 4: Reservas de emergencia en días (Eurostat nrg_stk_oem) ---
    panel_reservas_emergencia()

    # --- PASO 5: Origen del gas importado (Eurostat nrg_ti_gasm) ---
    panel_origen_gas()


if __name__ == "__main__":
    main()
