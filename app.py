"""
Monitor Energético Europa/Ormuz — Dashboard principal.

Visualiza el estado actual de la seguridad energética europea bajo el
contexto del conflicto del Estrecho de Ormuz (inicio 28-feb-2026):
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
from data.eia_client import (
    fetch_brent_spot, fetch_spr_stocks, fetch_comercial_stocks,
    fetch_destilado_stocks, fetch_jet_stocks,
)
from data.gie_client import get_client, fetch_gas_storage
from data.portwatch_client import fetch_chokepoint_flows
from data.transform import (
    transform_eia, transform_portwatch, transform_gas,
    transform_reservas_emergencia, transform_origen_gas,
    NOMBRES_PAISES_UE, NOMBRES_GEO, calcular_autonomias_spr, EstadoSPR
)
from data.eurostat_client import (
    fetch_reservas_emergencia, fetch_origen_gas,
)
from utils.charts import plot_reservas_emergencia, plot_origen_gas


# Configuración de la página (debe ser la primera llamada a st)
st.set_page_config(
    page_title="Monitor Energético Ormuz",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CONSTANTES DE NEGOCIO (NIVEL DE MÓDULO) ---
SUELO_TECNICO_SPR = 150000.0          # En miles de barriles (150M bbl)
SUELO_OPERATIVO_COMERCIAL = 250000.0   # En miles de barriles (250M bbl)


def panel_brent() -> None:
    """Panel autocontenido para la serie temporal del Brent Spot vs Reservas (SPR y Comerciales)."""
    st.subheader("Evolución de Reservas de Crudo de EEUU vs. Precio del Brent")

    API_KEY = st.secrets['EIA_API_KEY']
    # 1. Extracción (Bruto)
    data_brent_bruto = fetch_brent_spot(API_KEY)
    data_reservas_bruto = fetch_spr_stocks(API_KEY)
    data_comercial_bruto = fetch_comercial_stocks(API_KEY)

    # 2. Transformación 
    data_brent = transform_eia(data_brent_bruto)
    data_reservas = transform_eia(data_reservas_bruto)
    data_reservas_comerciales = transform_eia(data_comercial_bruto)

    # --- Cálculo de Autonomía SPR ---
    res = calcular_autonomias_spr(data_reservas, suelo_tecnico=SUELO_TECNICO_SPR)
    
    # Consumo del contrato semántico unificado: Typo imposible
    if res["estado"] != EstadoSPR.SIN_DATOS:
        col1, col2, col3 = st.columns(3)
        dias_v = res["dias_ventana"]
        
        with col1:
            if res["estado"] == EstadoSPR.DRENANDO:
                dias = res["dias_restantes"]
                value_text = f"{dias} días" if dias <= 90 else f"{dias} días (≈{int(dias/30)} meses)"
                st.metric(
                    label="Autonomía sobre suelo técnico",
                    value=value_text
                )
            elif res["estado"] == EstadoSPR.ESTABLE:
                st.metric(
                    label="Autonomía sobre suelo técnico",
                    value="—",
                    help=f"Sin drawdown neto en los últimos {dias_v} días"
                )
                
        with col2:
            nivel_m_bbl = res["ultimo_nivel"] / 1000.0
            delta_m_bbl = res["delta_ultimo"] / 1000.0
            st.metric(
                label="Nivel actual SPR",
                value=f"{nivel_m_bbl:.1f} M bbl",
                delta=f"{delta_m_bbl:+.1f} M bbl en {res['dias_delta_ultimo']} días"
            )
            
        with col3:
            ritmo_kbbl_dia = abs(res["ritmo_diario"])
            st.metric(
                label=f"Ritmo últimos {dias_v} días",
                value=f"{ritmo_kbbl_dia:,.0f} kbbl/día"
            )
            
        # Rótulo de riesgo dinámico y honesto
        ultima_fecha_str = data_reservas.index.max().strftime('%d-%b-%Y')
        st.caption(
            f"Proyección lineal al ritmo de variación medido en los últimos {dias_v} días — no constituye una predicción. "
            f"Suelo técnico de seguridad analítico: {SUELO_TECNICO_SPR/1000:.0f} M bbl. Último dato actualizado al {ultima_fecha_str}."
        )
    else:
        st.caption("⚠️ Datos históricos insuficientes o inconsistentes para estimar métricas de autonomía.")

    # 3. Renderizado (Visualización) con escala corregida
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Serie 1: Reserva Estratégica (M bbl)
    fig.add_trace(
        go.Scatter(
            x=data_reservas.index,
            y=data_reservas["value"] / 1000.0,
            name="Reserva Estratégica (SPR)",
            mode="lines",
            line=dict(color="#1D3557", width=2.5)
        ),
        secondary_y=False
    )

    # Serie 2: Reservas Comerciales (M bbl)
    fig.add_trace(
        go.Scatter(
            x=data_reservas_comerciales.index,
            y=data_reservas_comerciales["value"] / 1000.0,
            name="Reservas Comerciales",
            mode="lines",
            line=dict(color="#457B9D", width=2)
        ),
        secondary_y=False
    )

    # Serie 3: Precio del Brent
    fig.add_trace(
        go.Scatter(
            x=data_brent.index,
            y=data_brent["value"],
            name="Precio Brent",
            mode="lines",
            line=dict(color="#E63946", width=2)
        ),
        secondary_y=True
    )

    fig.update_layout(
    hovermode="x unified",  # ✅ Corregido a minúsculas
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02, 
        x=0, 
        xanchor="left"
    )
)
    fig.update_yaxes(title_text="<b>Reservas</b> [Millones de barriles]", secondary_y=False)
    fig.update_yaxes(title_text="<b>Precio Brent</b> [USD/barril]", secondary_y=True)

    # 5. Línea vertical del conflicto
    fig.add_vline(x="2026-02-28", line_width=2, line_dash="dash", line_color="orange")
    fig.add_annotation(
        x="2026-02-28", y=1, yref="paper",
        text="Inicio Conflicto (28-Feb)", showarrow=True, arrowhead=1, ax=60, ay=-20
    )

    # 6. Mínimo crítico SPR
    fig.add_hline(
        y=SUELO_TECNICO_SPR / 1000.0, line_width=1.5, line_dash="dot", line_color="#1D3557",
        annotation_text=f"Mínimo crítico SPR ({SUELO_TECNICO_SPR/1000:.0f}M bbl)",
        annotation_position="top left"
    )

    # 7. Suelo operativo comercial
    fig.add_hline(
        y=SUELO_OPERATIVO_COMERCIAL / 1000.0, line_width=1.5, line_dash="dot", line_color="#457B9D",
        annotation_text=f"Suelo operativo comercial ({SUELO_OPERATIVO_COMERCIAL/1000:.0f}M bbl)",
        annotation_position="top left"
    )
    
    fig.update_layout(margin=dict(b=50))
    st.plotly_chart(fig, width='stretch')

    # 8. Nota al pie metodológica
    st.info (
        "⚠️ **Nota**: La Reserva Estratégica (SPR, serie EIA WCSSTUS1) es crudo estatal, liberable solo por autorización presidencial; "
        "su capacidad de extracción decae conforme se vacían las cavernas. Las reservas comerciales (EIA WCESTUS1, excluyen la SPR) "
        "son stock de trabajo en refinerías, terminales y oleoductos. Los dos suelos son referencias analíticas propias, no cifras oficiales: "
        f"{SUELO_TECNICO_SPR/1000:.0f}M bbl (extracción de la SPR ya degradada) y {SUELO_OPERATIVO_COMERCIAL/1000:.0f}M bbl (mínimo operativo comercial estimado: llenado de oleoductos y fondos de tanque). "
        "Brent: precio spot. El crudo conserva holgura sobre ambos suelos; la urgencia de suministro se mide en la cobertura de productos "
        "(destilado y jet), no representada en este panel."
    )

def panel_reservas_eu_gas() -> None:
    """Panel autocontenido para las reservas de gas subterráneo en España."""
    st.subheader("Reservas de gas en Europa — comparativa por año (AGSI+)")
    
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
        y="full", 
        color=df_limpio["año"].astype(str),
        labels={
            "full": "Nivel de llenado de gas [%]", 
            "fecha_normalizada": "Fecha [Día/Mes]", 
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
        hovertemplate="<b>Año %{fullData.name}</b><br>Fecha: %{x|%d-%b}<br>Nivel: %{y:.2f} %<extra></extra>"
    )
    st.plotly_chart(fig, width='stretch')
        
def panel_portwatch() -> None:
    """Panel estrella: Tránsito de petroleros en el Estrecho de Ormuz."""
    st.subheader("Flujos Marítimos: Estrecho de Ormuz (IMF PortWatch)")
    
    # 1. Extracción (Bruto)
    # El cliente de PortWatch o tu función mapeada para Ormuz
    df_bruto = fetch_chokepoint_flows("chokepoint6", 2025)
    
    # 2. Transformación (limpieza + media móvil 7 días en transform_portwatch)
    df_limpio = transform_portwatch(df_bruto)

    date_max = max(df_limpio.index).strftime("%d-%m-%Y")
    # 4. Renderizado
    # Usamos el índice (date) de forma continua en el eje X
    fig = px.line(
        df_limpio,
        x=df_limpio.index,
        y="n_tanker",
        labels={
            "date": "Fecha",
            "n_tanker": "Número de buques totales"
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
        y=df_limpio["n_tanker"].max(),
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

@st.fragment
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
        "**Nota:** Autonomía del stock de emergencia de crudo y productos petrolíferos (Directiva 2009/119/CE). "
        "El umbral mínimo varía por país según el criterio aplicado: **90 días** sobre importaciones netas "
        "(mayoría de la UE), **61 días** sobre consumo interno para países con producción doméstica significativa "
        "(Dinamarca, Rumanía, Estonia, Croacia), y **92 días** en el caso de España por exigencia legal propia. "
        "La línea de referencia en cada gráfico refleja el mínimo específico del país seleccionado. Fuente: Eurostat (nrg_stk_oem)."
    )

@st.fragment
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


def panel_nivel_producto_us() -> None:
    """Panel: nivel de existencias de destilado y jet fuel en EEUU (EIA, semanal)."""
    st.subheader("Existencias comerciales de productos petrolíferos en EEUU")

    API_KEY = st.secrets['EIA_API_KEY']

    # 1. Extracción (Nivel absoluto en miles de barriles)
    df_dist_raw = fetch_destilado_stocks(API_KEY)
    df_jet_raw  = fetch_jet_stocks(API_KEY)

    # 2. Transformación
    dist = transform_eia(df_dist_raw)
    jet  = transform_eia(df_jet_raw)

    # Suelos de referencia analítica (Mínimos estructurales históricos de la industria)
    SUELO_DIST = 90000  # 90M bbl - Umbral crítico analítico
    SUELO_JET  = 30000  # 30M bbl - Stock mínimo estructural de trabajo

    CONFLICTO = "2026-02-28"

    # 3. Renderizado — Dos subplots por diferencias de escala (Destilado ~100M bbl vs Jet ~40M bbl)
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=["<b>Destilado (Gas oil / Diésel)</b>", "<b>Jet Fuel (Queroseno de aviación)</b>"],
        vertical_spacing=0.15,
    )

    # ── Subplot 1: Destilado ──
    fig.add_trace(go.Scatter(
        x=dist.index, y=dist['value'],
        name="Destilado EEUU",
        mode="lines",
        line=dict(color="#1D3557", width=2.5),
    ), row=1, col=1)

    fig.add_hline(
        y=SUELO_DIST, line_width=1.5, line_dash="dot", line_color="#1D3557",
        annotation_text=f"Suelo operativo estimado (90M bbl) ",
        annotation_position="top right",
        row=1, col=1,
    )

    # ── Subplot 2: Jet Fuel ──
    fig.add_trace(go.Scatter(
        x=jet.index, y=jet['value'],
        name="Jet EEUU",
        mode="lines",
        line=dict(color="#457B9D", width=2),
    ), row=2, col=1)

    fig.add_hline(
        y=SUELO_JET, line_width=1.5, line_dash="dot", line_color="#457B9D",
        annotation_text=f"Suelo operativo estimado (30M bbl) ",
        annotation_position="top right",
        row=2, col=1,
    )

    # ── Elementos globales del layout ──
    
    # Línea vertical del conflicto cruzando todos los subplots
    fig.add_vline(x=CONFLICTO, line_width=1.5, line_dash="dash", line_color="orange", row="all", col="all")
    
    # Anotación del conflicto en la parte superior del lienzo
    fig.add_annotation(
        x=CONFLICTO, y=1.02, yref="paper",
        text="Inicio Conflicto (28-Feb)", showarrow=True, arrowhead=1, ax=60, ay=-15,
    )

    # Rotulación de ejes
    fig.update_yaxes(title_text="<b>Existencias</b> (Kbbl)", row=1, col=1)
    fig.update_yaxes(title_text="<b>Existencias</b> (Kbbl)", row=2, col=1)
    fig.update_xaxes(title_text="", row=2, col=1)

    fig.update_layout(
        hovermode="x unified",
        legend=dict(
            orientation="h", 
            yanchor="bottom", 
            y=1.08, 
            x=0, 
            xanchor="left"
        ),
        margin=dict(b=40), # Reducido a 40 para dejar una separación limpia con el st.info
    )

    # Renderizado del gráfico
    st.plotly_chart(fig, width='stretch')

    # 4. Nota explicativa nativa de Streamlit (Evita truncamientos y mejora UI)
    st.info(
        "**Nota:** Las series de la EIA representan los inventarios comerciales netos de producto "
        "refinado en suelo estadounidense. Los suelos de 90M bbl (Destilados) y 30M bbl (Jet Fuel) "
        "son referencias analíticas propias basadas en los límites operativos mínimos históricos "
        "(*tank bottoms* y *line fill* estructural) por debajo de los cuales aparecen disrupciones "
        "severas en la distribución capilar. A diferencia del crudo, estas series reflejan la "
        "urgencia real de suministro a corto plazo tras el cierre de Ormuz."
    )

def main() -> None:
    """Punto de entrada del dashboard."""
    st.title("Monitor Energético Europa/Ormuz")
    st.text(
    "¿Cómo de expuesto está el suministro energético europeo al cierre del "
    "Estrecho de Ormuz, y cuánto colchón queda? Dashboard de seguridad "
    "energética con datos físicos verificables — flujos marítimos, Brent, "
    "reservas de crudo y gas — de IMF PortWatch, EIA, GIE AGSI+ y Eurostat, "
    "actualizados automáticamente desde el inicio del conflicto (28-feb-2026)."
    )
    # --- PASO 1: El estrecho de Ormuz ---
    panel_portwatch()

    # --- PASO 2: Brent+ reservas petróleo de EEUU ---
    panel_brent()
    
    # --- PASO 3: Reservas de gas EU ---
    panel_reservas_eu_gas()

    # --- PASO 4: Reservas de emergencia en días (Eurostat nrg_stk_oem) ---
    panel_reservas_emergencia()

    # --- PASO 5: Origen del gas importado (Eurostat nrg_ti_gasm) ---
    panel_origen_gas()

    # --- PASO 6: Nivel de existencias de producto en EEUU (EIA semanal) ---
    panel_nivel_producto_us()

    # --- PASO 7: Metodología
    with st.expander("📋 Metodología y limitaciones"):
        st.markdown("""
        **Fuentes y frecuencias**
        | Fuente | Dato | Frecuencia |
        |---|---|---|
        | IMF PortWatch | Tráfico marítimo (señales AIS) | Diaria |
        | EIA | Brent spot | Diaria |
        | EIA | Reservas de crudo (SPR y comerciales) y productos | Semanal |
        | GIE AGSI+ | Reservas de gas subterráneo | Diaria |
        | Eurostat | Reservas de emergencia y origen del gas | Mensual |

        **Desfases de publicación**
        - Las series semanales de la EIA llegan con 2–3 días de retraso sobre el período que cubren.
        - Los datasets mensuales de Eurostat llegan con varios meses de desfase: los últimos
        movimientos (p. ej. la liberación coordinada de reservas de la IEA) aún no aparecen
        reflejados en los paneles basados en Eurostat.
        - Los datos AIS de PortWatch están afectados por interferencias GPS (*jamming*) en la zona
        del Golfo desde febrero de 2026 y por buques que apagan o falsean el transpondedor
        (*spoofing*). El tráfico observado es un suelo, no una cifra exacta.

        **Umbrales y proyecciones**
        - Los suelos marcados en los paneles (SPR 150 M bbl, comerciales 250 M bbl, destilado
        90 M bbl, jet 30 M bbl) son **referencias analíticas propias**, no límites oficiales.
        La única referencia normativa es la Directiva 2009/119/CE: 90 días de importaciones
        netas o 61 días de consumo, según país.
        - Las autonomías en días son **proyecciones lineales al ritmo observado**, no predicciones.
        - Los días de cobertura no son aditivos entre países: cada cifra se calcula sobre el
        consumo o importación de su propio país.

        **Qué NO mide este monitor**
        - No predice precios ni escenarios futuros.
        - No establece causalidad: los movimientos se describen como *consistentes con* el
        contexto, no como consecuencia probada.
        - No cubre flujos de refino, mercado spot de LNG ni contratos bilaterales — solo
        magnitudes físicas públicas.
        """)
        
if __name__ == "__main__":
    main()
