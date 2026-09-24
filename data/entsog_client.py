"""
Cliente para el API público de ENTSOG Transparency Platform (gas por gasoducto).

Sin API key: es un dato público (Fase 0 del pliego «panel-gasoductos», punto 6).
No hay un límite de peticiones/minuto documentado para ENTSOG (el "400/min"
que aparece en búsquedas genéricas es de ENTSO-E, la plataforma de
electricidad, una API distinta que sí exige token). Lo único documentado:
máximo 60s de ejecución por consulta.

Dos indicadores por punto: 'Physical Flow' (flujo físico medido) y
'Nomination' (gas nominado, lo que declaran las partes que va a fluir). La
combinación de ambos, punto a punto, es lo que permite distinguir una parada
real de un hueco de reporte (ver `data.transform.regla_calidad_entsog`).

Mapa de puntos de entrada
--------------------------
`MAPA_PUNTOS_ENTRADA` es el resultado de la Fase 0 del pliego (aprobado por
Laura en dos pasadas: PARADA 1 con correcciones). Cada entrada es un punto de
entrada a la UE desde un país de fuera de la UE, con su origen físico real
(no el país fronterizo) y una fuente pública. Deliberadamente NO incluye:

  - las reentradas y otras exclusiones estructurales (gas que ya entró en la
    UE y vuelve a entrar, sin capacidad técnica, sin fuente de origen, etc.
    — ver `PUNTOS_REENTRADA_EXCLUIDOS` abajo);
  - los puntos sin ningún valor publicado en 'Physical Flow' dirección
    entrada, ya sea porque la API nunca devuelve fila (404 permanente:
    Emden NPT GUD/Thyssengas, Imatra, Beregdaróc, Mediesu Aurit — en
    `PUNTOS_REENTRADA_EXCLUIDOS`) o porque devuelve filas con valor
    siempre nulo o la serie se corta en una fecha conocida (Tarifa, Narva,
    Värska, Luhamaa, South North CSEP — en `PUNTOS_SIN_DATOS_PUBLICADOS`,
    con la fecha del último dato real de cada uno). Incluir cualquiera de
    estos dejaría su origen en vacío TODOS los días desde que falta el
    dato, por la regla de "cualquier punto vacío vacía el origen-día"
    (Fase 2, punto 4 del pliego);
  - los operadores duplicados de un mismo punto físico (Fase 0, punto 5):
    de cada grupo de valores idénticos se deja solo uno, el de menos huecos
    en 2025-2026 (recuento pegado en el chat de la PARADA 1).
"""

from __future__ import annotations

from collections import namedtuple

import pandas as pd
import requests
import streamlit as st


ENTSOG_OPERATIONALDATA_URL = "https://transparency.entsog.eu/api/v1/operationaldata"

PuntoEntrada = namedtuple(
    "PuntoEntrada", ["point_key", "operator_key", "etiqueta", "origen", "grupo_fisico"],
    defaults=[None],
)
# `grupo_fisico`: solo se rellena cuando varios operadores del mapa
# declaran el MISMO punto físico (ej. Emden EPT1: GUD/OGE/GTS). La regla de
# calidad se aplica al TOTAL del grupo, no a cada operador por separado —
# ver `data.transform._ensamblar_largo` y el diagnóstico de la PARADA 3
# (Emden OGE en 0 con GTS al doble de lo normal: el gas se redistribuyó
# dentro del punto, no desapareció). `None` (el resto de puntos) se agrupa
# consigo mismo, por `point_key`.


@st.cache_data(ttl=21600)
def fetch_punto(
    point_key: str,
    operator_key: str,
    indicator: str,
    direction: str = "entry",
    start: str = "2025-01-01",
    end: str | None = None,
) -> pd.Series:
    """Descarga un indicador diario de un punto de entrada a la UE.

    Args:
        point_key: identificador ENTSOG del punto (ej. 'ITP-00106').
        operator_key: identificador del operador que declara ese punto (ej.
            'BE-TSO-0001') — el mismo punto físico puede tener varios
            operadores declarando cada uno el suyo.
        indicator: 'Physical Flow' o 'Nomination'.
        direction: 'entry' (por defecto) o 'exit' — el flujo en sentido
            contrario, solo tiene sentido pedirlo para los puntos de
            `PUNTOS_DOBLE_SENTIDO` (ver `data.transform.regla_calidad_entsog`).
        start: fecha de inicio (YYYY-MM-DD). Por defecto 1-1-2025 (pliego).
        end: fecha de fin (None = hoy).

    Returns:
        pd.Series de kWh/d (float), indexada por fecha (datetime, ordenada,
        nombre 'fecha'). Vacía si ENTSOG no tiene ninguna fila publicada para
        esta combinación punto/operador/indicador/dirección en el rango
        pedido (404 "No result found") — no es un fallo de red, es ausencia
        de datos publicados (comprobado en Fase 0 y Fase 2 para varios
        puntos, ver módulo).
    """
    if end is None:
        end = pd.Timestamp.today().strftime("%Y-%m-%d")

    params = {
        "pointKey": point_key,
        "operatorKey": operator_key,
        "directionKey": direction,
        "indicator": indicator,
        "periodType": "day",
        "from": start,
        "to": end,
        "limit": 2000,
    }
    response = requests.get(ENTSOG_OPERATIONALDATA_URL, params=params, timeout=60)

    if response.status_code == 404:
        return pd.Series(dtype="float64", index=pd.DatetimeIndex([], name="fecha"))

    response.raise_for_status()
    filas = response.json()["operationaldata"]
    df = pd.DataFrame(filas)
    df["fecha"] = pd.to_datetime(df["periodFrom"].str[:10])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    serie = df.set_index("fecha")["value"].sort_index()
    return serie


# ── Mapa de puntos incluidos (Fase 0, aprobado PARADA 1 + correcciones) ─────

MAPA_PUNTOS_ENTRADA = [
    # ── Noruega ── directo, sin tránsito por terceros. Fuente: Gassco, mapa
    # de transporte (https://gassco.eu/en/transport-map/) — Zeebrugge,
    # Dunkerque, Emden y Dornum son las terminales de recepción de Gassco en
    # el continente. Emden EPT1: de los 3 operadores, GUD y Thyssengas
    # declaraban el mismo flujo (duplicado); se queda GUD (0 huecos en
    # 2025-2026 frente a 1 de Thyssengas) más OGE (flujo distinto, se suma)
    # más GTS del lado neerlandés (punto físico aparte).
    PuntoEntrada("ITP-00106", "BE-TSO-0001", "Zeebrugge ZPT", "Noruega"),
    PuntoEntrada("ITP-00045", "FR-TSO-0003", "Dunkerque", "Noruega"),
    PuntoEntrada("ITP-00630", "DK-TSO-0001", "North Sea Entry", "Noruega"),
    PuntoEntrada("ITP-00081", "DE-TSO-0005", "Emden (EPT1) GUD", "Noruega", grupo_fisico="Emden (EPT1)"),
    PuntoEntrada("ITP-00080", "DE-TSO-0009", "Emden (EPT1) OGE", "Noruega", grupo_fisico="Emden (EPT1)"),
    PuntoEntrada("ITP-00160", "NL-TSO-0001", "Emden (EPT1) GTS", "Noruega", grupo_fisico="Emden (EPT1)"),
    PuntoEntrada("ITP-00188", "DE-TSO-0005", "Dornum (NETRA) GUD", "Noruega"),

    # ── Rusia ── directo o vía tránsito documentado punto a punto.
    # Greifswald/Nord Stream: sin flujo desde el sabotaje de sep-2022 y las
    # sanciones — se mantiene en 0 (parada real) por si se reactiva; de los 3
    # operadores idénticos (todos en 0) se queda GUD, mismo criterio de
    # consistencia que en Emden.
    PuntoEntrada("ITP-00491", "DE-TSO-0005", "Greifswald / GUD (Nord Stream)", "Rusia"),
    # Strandzha 2 / Malkoclar: continuación terrestre confirmada de TurkStream
    # (https://en.wikipedia.org/wiki/TurkStream).
    PuntoEntrada("ITP-00549", "BG-TSO-0001", "Strandzha 2 / Malkoclar (TurkStream)", "Rusia"),
    # Estonia-Rusia (Narva, Värska, Luhamaa) NO están aquí — ver
    # PUNTOS_SIN_DATOS_PUBLICADOS. "Rusia" queda cubierto por Greifswald y
    # Strandzha 2, que sí tienen serie completa.

    # ── Turquía (mixto) ── el Reglamento (UE) 2026/261 exige probar que el
    # gas de Strandzha (1) no es de origen ruso, mezclado en el mismo sistema
    # turco que declara azerí (BTA, ver informe PARADA 1). Kipi (DESFA): flujo
    # real en 0 en 2025-2026, se mantiene por decisión de Laura.
    PuntoEntrada("ITP-00041", "BG-TSO-0001", "Strandzha / Malkoclar", "Turquía (mixto)"),
    PuntoEntrada("ITP-00046", "GR-TSO-0001", "Kipi (DESFA)", "Turquía (mixto)"),

    # ── Azerbaiyán, vía TAP ── punto propio de TAP AG en Kipoi (frontera
    # grecoturca), no las salidas internas de la misma tubería hacia
    # Bulgaria/Italia/norte de Grecia (esas se excluyen, ver abajo, para no
    # contar el mismo gas dos veces). TAP AG está registrado como operador de
    # país CH (Suiza, su domicilio social) en ENTSOG — artefacto
    # administrativo, no el origen del gas. Ruta física: Shah Deniz II
    # (Azerbaiyán) vía TANAP-TAP.
    PuntoEntrada("ITP-00274", "AL-TSO-0001", "Kipoi (TAP)", "Azerbaiyán"),

    # ── Argelia ──
    PuntoEntrada("ITP-00048", "ES-TSO-0006", "Almería (Medgaz)", "Argelia"),
    PuntoEntrada("ITP-00093", "IT-TSO-0001", "Mazara del Vallo (Transmed, vía Túnez)", "Argelia"),
    # Tarifa (GME, vía Marruecos) NO está aquí — ver PUNTOS_SIN_DATOS_PUBLICADOS.
    # Laura decidió mantenerlo en el inventario de la Fase 0 ("Tarifa se
    # queda"), pero su último dato real es del 2-dic-2024: desde entonces no
    # publica NINGÚN valor, ni físico ni nominado. Incluirlo en la suma
    # dejaría "Argelia" vacío TODOS los días desde esa fecha.

    # ── Libia ── conexión directa, sin tránsito por terceros (Greenstream).
    PuntoEntrada("ITP-00074", "IT-TSO-0001", "Gela (Greenstream)", "Libia"),

    # ── Reino Unido (mixto) ── producción propia + gas noruego + GNL, sin
    # repartir (regla explícita del pliego).
    PuntoEntrada("ITP-00061", "BE-TSO-0001", "Zeebrugge IZT", "Reino Unido (mixto)"),
    PuntoEntrada("ITP-00495", "IE-TSO-0002", "Moffat", "Reino Unido (mixto)"),
    PuntoEntrada("ITP-00207", "UK-TSO-0004", "Bacton (BBL)", "Reino Unido (mixto)"),
    # South North CSEP NO está aquí — ver PUNTOS_SIN_DATOS_PUBLICADOS: sin
    # ningún valor publicado en todo el histórico comprobado.

    # ── Ucrania (origen sin determinar) ── el tránsito de gas ruso vía
    # Ucrania cesó el 1-ene-2025 (acuerdo Gazprom-Naftogaz no renovado); se
    # mantienen en el mapa en 0 (parada real) por si se reactivan. Por
    # decisión de Laura, etiqueta neutra en vez de "Rusia": el origen del gas
    # que pudiera volver a fluir no está determinado de antemano.
    PuntoEntrada("ITP-10006", "HU-TSO-0001", "VIP Bereg", "Ucrania (origen sin determinar)"),
    PuntoEntrada("ITP-00087", "RO-TSO-0001", "Isaccea I", "Ucrania (origen sin determinar)"),
    PuntoEntrada("ITP-00299", "RO-TSO-0001", "Isaccea II", "Ucrania (origen sin determinar)"),
    PuntoEntrada("ITP-00300", "RO-TSO-0001", "Isaccea III", "Ucrania (origen sin determinar)"),
    PuntoEntrada("ITP-00438", "RO-TSO-0001", "VIP Mediesu Aurit - Isaccea", "Ucrania (origen sin determinar)"),
    PuntoEntrada("ITP-00421", "SK-TSO-0001", "Budince", "Ucrania (origen sin determinar)"),
    PuntoEntrada("ITP-00117", "SK-TSO-0001", "Uzhhorod - Velké Kapušany", "Ucrania (origen sin determinar)"),
    PuntoEntrada("ITP-10008", "PL-TSO-0002", "GCP GAZ-SYSTEM/UA TSO", "Ucrania (origen sin determinar)"),
]


# ── Puntos de doble sentido (PARADA 3, regla de sentido contrario) ─────────
# Comprobado contra operatorpointdirections (pointKey+operatorKey, con y sin
# filtro de dirección): estos son los puntos del mapa que tienen registrada
# TANTO 'entry' como 'exit'. Solo para estos tiene sentido descargar el
# flujo físico de salida y aplicar la regla de sentido contrario (flujo de
# entrada 0 + nominación > 0 + flujo de SALIDA > 0 ese mismo día => 0 real,
# no vacío — ver `data.transform.regla_calidad_entsog`). Los 7 puntos del
# mapa que faltan aquí (Dunkerque, North Sea Entry, Greifswald/GUD,
# Strandzha 2, Almería/Medgaz, Mazara del Vallo, Gela) solo tienen 'entry'
# registrado: no hay flujo de salida que pedir.
PUNTOS_DOBLE_SENTIDO = {
    "ITP-00106",  # Zeebrugge ZPT
    "ITP-00081",  # Emden (EPT1) GUD
    "ITP-00080",  # Emden (EPT1) OGE
    "ITP-00160",  # Emden (EPT1) GTS
    "ITP-00188",  # Dornum (NETRA) GUD
    "ITP-00041",  # Strandzha / Malkoclar
    "ITP-00046",  # Kipi (DESFA)
    "ITP-00274",  # Kipoi (TAP)
    "ITP-00061",  # Zeebrugge IZT
    "ITP-00495",  # Moffat
    "ITP-00207",  # Bacton (BBL)
    "ITP-10006",  # VIP Bereg
    "ITP-00087",  # Isaccea I
    "ITP-00299",  # Isaccea II
    "ITP-00300",  # Isaccea III
    "ITP-00438",  # VIP Mediesu Aurit - Isaccea
    "ITP-00421",  # Budince
    "ITP-00117",  # Uzhhorod - Velké Kapušany
    "ITP-10008",  # GCP GAZ-SYSTEM/UA TSO
}


# ── Reentradas y otras exclusiones estructurales (documentado, no usado en
# el cálculo) ── pointKey · motivo. Puntos sin serie de datos alguna (404
# permanente) están aquí también; los que SÍ tienen filas pero con valor
# nulo o una serie que se corta en una fecha conocida van en
# PUNTOS_SIN_DATOS_PUBLICADOS, más abajo. Ningún pointKey de esta lista debe
# aparecer en MAPA_PUNTOS_ENTRADA (tests/test_entsog.py lo comprueba).
PUNTOS_REENTRADA_EXCLUIDOS = [
    ("ITP-00228", "RC Basel (DE/CH): reentrada, gas que ya entró en la UE transita Suiza (Transitgas)."),
    ("ITP-00229", "RC Thayngen-Fallentor (DE/CH): reentrada, ídem."),
    ("ITP-00544", "VIP Germany-CH (DE/CH): reentrada, ídem."),
    ("ITP-00294", "Wallbach (DE/CH): reentrada, ídem; sin datos publicados en esta dirección."),
    ("ITP-00039", "Oltingue (FR/CH): reentrada, ídem."),
    ("ITP-00281", "Jura (FR/CH): reentrada, ídem; sin datos publicados en esta dirección."),
    ("ITP-00136", "Griespass/Passo Gries (IT/CH): reentrada explícita del pliego, flujo real confirmado."),
    ("ITP-00008", "Melendugno - IT/TAP: salida interna de TAP, ya contada en Kipoi (ITP-00274)."),
    ("ITP-00275", "Komotini - TAP/IGB: salida interna de TAP, ya contada en Kipoi (ITP-00274)."),
    ("ITP-00427", "Nea Mesimvria: salida interna de TAP, ya contada en Kipoi (ITP-00274)."),
    ("ITP-00036", "Kyustendil/Zidilovo (BG/MK): reentrada, Macedonia del Norte no produce gas propio."),
    ("ITP-00529", "Kireevo/Zaychar (BG/RS): sin capacidad técnica documentada en sentido RS->BG."),
    ("ITP-00134", "Kalotina/Dimitrovgrad (BG/RS): sin fuente clara del origen real, sin flujo confirmado."),
    ("ITP-00154", "Ungheni (RO/MD): reentrada, Moldavia no produce gas propio; flujo real dominante es RO->MD."),
    ("ITP-10013", "Kiskundorozsma-2 (HU/RS): reentrada de TurkStream, ya contada en Strandzha 2 (decisión Laura)."),
    ("ITP-00085", "Kotlovka (LT/BY): tránsito a Kaliningrado, no importación a la UE (decisión Laura)."),
    ("ITP-00024", "Imatra (FI/RU): sin serie de datos en Physical Flow, dirección entrada (404 permanente)."),
    ("ITP-00095", "Beregdaróc (HU/UA): sin serie de datos en Physical Flow, dirección entrada (404 permanente)."),
    ("ITP-00084", "Mediesu Aurit (RO/UA): sin serie de datos en Physical Flow, dirección entrada (404 permanente)."),
    ("ITP-00086", "Emden (NPT) GUD (DE/NO): sin serie de datos en Physical Flow, dirección entrada (404 permanente)."),
    ("ITP-00075", "Emden (NPT) Thyssengas (DE/NO): sin serie de datos en Physical Flow, dirección entrada (404 permanente)."),
    ("ITP-00161", "Emden (NPT) GTS (NL/NO): sin serie de datos en Physical Flow, dirección entrada (404 permanente)."),
    ("ITP-00105", "Emden (EPT1) Thyssengas (DE/NO): operador duplicado de GUD (mismo flujo, más huecos)."),
    ("ITP-00126", "Dornum (NETRA) OGE (DE/NO): operador duplicado de GUD (mismo flujo, empate de huecos)."),
    ("ITP-00525", "Dornum (NETRA) GASPOOL (DE/NO): operador duplicado de GUD (mismo flujo, empate de huecos)."),
    ("ITP-00247", "Greifswald / NEL (DE/RU): operador duplicado de GUD (mismo flujo -0-, empate de huecos)."),
    ("ITP-00297", "Greifswald / Fluxys Deutschland (DE/RU): operador duplicado de GUD (mismo flujo -0-, empate de huecos)."),
]


# ── Puntos sin datos publicados (categoría propia, distinta de reentrada) ──
# pointKey · motivo · fecha del último dato real (Physical Flow, no NaN).
# "Ninguno conocido" cuando la API nunca ha devuelto una fila con valor para
# ese punto/operador/dirección, en todo el histórico comprobado (hasta 2021;
# antes de esa fecha ENTSOG no devuelve ni filas — 404).
#
# Ningún pointKey de esta lista debe aparecer en MAPA_PUNTOS_ENTRADA (mismo
# test que para PUNTOS_REENTRADA_EXCLUIDOS).
PuntoSinDatos = namedtuple("PuntoSinDatos", ["point_key", "motivo", "fecha_ultimo_dato"])

PUNTOS_SIN_DATOS_PUBLICADOS = [
    PuntoSinDatos(
        "ITP-00082",
        "Tarifa (ES/MA): en el inventario por decisión de Laura, pero excluido del cálculo — incluirlo "
        "dejaría 'Argelia' vacío todos los días desde dic-2024 por la regla de origen-día.",
        "2024-12-02",
    ),
    PuntoSinDatos(
        "ITP-00243",
        "Narva (EE/RU): sin ninguna fila en Physical Flow después de esta fecha (no 0 — ausencia total, "
        "la serie se corta). Excluido para no vaciar 'Rusia' desde entonces.",
        "2025-12-07",
    ),
    PuntoSinDatos(
        "ITP-00187",
        "Värska (EE/RU): mismo patrón que Narva, la serie se corta el mismo día.",
        "2025-12-07",
    ),
    PuntoSinDatos(
        "ITP-00493",
        "Luhamaa (EE/RU): ninguna fila con valor en Physical Flow en todo el histórico comprobado "
        "(2021-2026); antes de 2021 ENTSOG no devuelve ni filas para este punto.",
        "ninguno conocido",
    ),
    PuntoSinDatos(
        "ITP-00222",
        "South North CSEP (IE/UK): mismo patrón que Luhamaa, ninguna fila con valor desde 2021.",
        "ninguno conocido",
    ),
]
