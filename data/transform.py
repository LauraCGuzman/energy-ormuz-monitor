import logging

import pandas as pd
from gie.agsi_mappings import AGSICountry

COLUMNA_CAPACIDAD_GAS = "workingGasVolume"
COLUMNA_STOCK_GAS = "gasInStorage"
COLUMNA_LLENADO_GAS = "full"


def _formatear_fechas(indice):
    """`YYYY-MM-DD` de cada fecha del índice; si son más de 5, las 3 primeras y el total."""
    fechas = [f.strftime("%Y-%m-%d") for f in indice]
    if len(fechas) <= 5:
        return ", ".join(fechas)
    return ", ".join(fechas[:3]) + f", ... ({len(fechas)} en total)"


def _capa_capacidad(df, pais):
    """Capa 1 de calidad: descarta la fila entera si `workingGasVolume` es 0 o NaN.

    `gie-py` convierte el '-' de la API en 0, no en NaN (`_fix_dataframe`),
    así que un hueco de reporte es indistinguible por tipo de un cero real.

    El discriminador es `workingGasVolume`: un país con almacenamiento nunca
    tiene capacidad 0 — es imposible por definición, no improbable. Si la
    capacidad es 0 o NaN, ese día no se reportó y la fila entera se cae.

    `full` y `gasInStorage` NO se tocan aquí: un 0 real tiene que seguir
    viéndose (caso de los días de Suecia con stock genuinamente bajo).
    """
    if COLUMNA_CAPACIDAD_GAS not in df.columns:
        # transform_gas también sirve a ALSI (GNL), que no tiene esta
        # columna: ausencia esperada por la fuente, no una anomalía — no-op
        # silencioso, sin aviso.
        return df

    capacidad = pd.to_numeric(df[COLUMNA_CAPACIDAD_GAS], errors="coerce")
    valido = capacidad.notna() & (capacidad > 0)

    descartadas = df.index[~valido]
    if len(descartadas):
        n = len(descartadas)
        logging.warning(
            "[calidad_gas/capacidad] %s: %d fila%s descartada%s por workingGasVolume<=0 o NaN - %s",
            pais, n, "" if n == 1 else "s", "" if n == 1 else "s", _formatear_fechas(descartadas),
        )

    return df.loc[valido]


def _capa_vecinos(df, pais):
    """Capa 2 de calidad: anula solo `full` en los días con `gasInStorage`
    anómalo respecto a sus vecinos cronológicos inmediatos.

    Actúa sobre lo que sobrevive a `_capa_capacidad`. Un día suelto puede
    llegar con un valor de `gasInStorage` muy alejado del día anterior Y del
    siguiente, que además coinciden EXACTAMENTE entre sí (mismo decimal antes
    y después). Físicamente eso no pasa — una caída y recuperación reales no
    devuelven el stock al mismo dato exacto — así que es un hueco de
    captura, no un vaciado real.
    """
    if COLUMNA_STOCK_GAS not in df.columns or COLUMNA_LLENADO_GAS not in df.columns:
        # transform_gas también sirve a ALSI (GNL), que no tiene
        # 'gasInStorage' (tiene 'lngInventory' en su lugar): ausencia
        # esperada por la fuente, no una anomalía — no-op silencioso, sin aviso.
        return df

    stock = df[COLUMNA_STOCK_GAS]
    anterior = stock.shift(1)
    siguiente = stock.shift(-1)
    mismo_entorno = (anterior - siguiente).abs() < 1e-9
    lejos_del_entorno = (stock - anterior).abs() > 0.2 * anterior.abs().clip(lower=1e-9)
    hueco = mismo_entorno & lejos_del_entorno & anterior.notna() & siguiente.notna()

    afectadas = df.index[hueco]
    if len(afectadas):
        n = len(afectadas)
        logging.warning(
            "[calidad_gas/vecinos] %s: %d valor%s de 'full' anulado%s por stock anómalo - %s",
            pais, n, "es" if n != 1 else "", "s" if n != 1 else "", _formatear_fechas(afectadas),
        )

    df.loc[hueco, COLUMNA_LLENADO_GAS] = float("nan")
    return df


def _calidad_gas(df, pais):
    """Aplica las dos capas de calidad de AGSI+ en orden fijo. Devuelve el df filtrado.

    Orden fijo y no negociable: capacidad primero (descarta filas), vecinos
    después, sobre lo que sobrevive a la capacidad (anula solo `full`). El
    orden importa: la capa de capacidad cambia quiénes son los vecinos
    cronológicos de cada día para la capa de vecinos.

    `transform_gas` sirve tanto a AGSI (reservas) como a ALSI (GNL); ALSI no
    tiene las columnas de ninguna capa, así que ambas no-opean en silencio
    (ver `_capa_capacidad` / `_capa_vecinos`) — no es una coincidencia entre
    capas, cada una lo comprueba por su cuenta.
    """
    df = _capa_capacidad(df, pais)
    df = _capa_vecinos(df, pais)
    return df


def transform_eia(data):
    # 1. Copiar para evitar mutación
    df = data.copy()

    # 2. Castear tipos ANTES del slice para evitar el SettingWithCopyWarning
    df["value"] = df["value"].astype("float")
    df["period"] = pd.to_datetime(df["period"], errors="coerce")

    # 3. Simplificar: quedarnos solo con period y value, tirando las 9 constantes
    df = df[["period", "value"]]

    # 4. Consistencia y estilo moderno (encadenado sin inplace)
    df = df.set_index("period").sort_index()

    return df


def transform_portwatch(data):
    # 1. Copiar para evitar mutación
    df = data.copy()

    # 2. Eliminar prefijo 'attributes.' de raíz en todas las columnas
    df.columns = df.columns.str.replace("attributes.", "", regex=False)

    # 3. Tirar redundancias, artefactos y las constantes de un fetch mono-chokepoint (portid, portname)
    columns_to_drop = ["ObjectId", "year", "month", "day", "portid", "portname"]
    df.drop(columns=columns_to_drop, errors="ignore", inplace=True)

    # 4. Castear fecha
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # 5. Consistencia y estilo moderno (encadenado sin inplace)
    df = df.set_index("date").sort_index()

    # 6. Media móvil 7 días para suavizar el ruido de fin de semana en los AIS
    df["n_tanker_smooth"] = df["n_tanker"].rolling(window=7, min_periods=1).mean()

    return df


# Diccionario único de chokepoints: portid (propiedad del dataset PortWatch,
# enumerados contra la API el 5/9, ver informe de Fase 0) -> nombre legible.
# Los seis aprobados para el selector del panel de PortWatch (pliego
# «selector-chokepoints»). Ormuz es el valor por defecto del panel.
NOMBRES_CHOKEPOINTS = {
    'chokepoint6': 'Estrecho de Ormuz',
    'chokepoint1': 'Canal de Suez',
    'chokepoint4': 'Bab el-Mandeb',
    'chokepoint5': 'Estrecho de Malaca',
    'chokepoint3': 'Estrecho del Bósforo',
    'chokepoint2': 'Canal de Panamá',
}

CHOKEPOINT_DEFECTO = 'chokepoint6'


def etiqueta_chokepoint(chokepoint_id: str) -> str:
    """Rótulo legible para un chokepoint, a partir del identificador solicitado.

    Deliberadamente no lee el DataFrame transformado: `transform_portwatch`
    descarta `portid`/`portname` por ser constantes en un fetch mono-chokepoint
    (paso 3 de arriba), así que el único origen fiable del rótulo es lo que se
    pidió, no una columna que ya no existe en el resultado.
    """
    return NOMBRES_CHOKEPOINTS.get(chokepoint_id, chokepoint_id)


def transform_gas(data, pais="?"):
    # 1. Copiar para evitar mutación
    df = data.copy()

    # 2. Eliminar gasDayEnd por redundancia (el índice ya es gasDayStart)
    df.drop(columns=["gasDayEnd"], errors="ignore", inplace=True)

    # 2.1. `query_gas_country`/`query_lng_country` devuelven gasDayStart en
    # orden DESCENDENTE (más reciente primero), sin ordenar — comprobado en
    # el índice crudo. No se nota en el gráfico (una serie monótona, aunque
    # invertida, sigue dibujando una línea limpia), pero las capas de calidad
    # de abajo comparan cada fila con su vecino real en el calendario, así
    # que necesitan orden cronológico explícito. Mismo motivo por el que el
    # suavizado de PortWatch se movió detrás del sort_index el 23/6.
    df = df.sort_index()

    # 2.2. Calidad AGSI+: dos capas en orden fijo, capacidad y vecinos (ver
    # `_calidad_gas`). No-op silencioso para datos de ALSI (panel de GNL),
    # que no tiene las columnas de ninguna de las dos.
    df = _calidad_gas(df, pais)

    # 3. Columna año real para agrupar/colorear
    df["año"] = df.index.year

    # 4. Crear la fecha normalizada (año bisiesto falso: 2024)
    # Usamos pd.to_datetime apoyándonos en el propio índice para evitar desalineaciones (NaN)
    df["fecha_normalizada"] = pd.to_datetime(
        "2024-" + df.index.strftime("%m-%d %H:%M:%S")
    )

    # Nota: Los numéricos ya vienen como float/int y 'status' se mantiene como str.
    return df


# Diccionario de nombres legibles para los países UE-27
NOMBRES_PAISES_UE = {
    'AT': 'Austria', 'BE': 'Bélgica', 'BG': 'Bulgaria', 'CY': 'Chipre',
    'CZ': 'Chequia', 'DE': 'Alemania', 'DK': 'Dinamarca', 'EE': 'Estonia',
    'EL': 'Grecia', 'ES': 'España', 'FI': 'Finlandia', 'FR': 'Francia',
    'HR': 'Croacia', 'HU': 'Hungría', 'IE': 'Irlanda', 'IT': 'Italia',
    'LT': 'Lituania', 'LU': 'Luxemburgo', 'LV': 'Letonia', 'MT': 'Malta',
    'NL': 'Países Bajos', 'PL': 'Polonia', 'PT': 'Portugal', 'RO': 'Rumanía',
    'SE': 'Suecia', 'SI': 'Eslovenia', 'SK': 'Eslovaquia'
}

NOMBRES_GEO = {**NOMBRES_PAISES_UE, 'EU27_2020': '🇪🇺 Unión Europea (UE-27)'}

# Países UE-27 con almacenamiento subterráneo de gas cubierto por AGSI+.
# Se deriva del enum de la librería (no se hardcodea a mano) para no
# desincronizarse si gie-py amplía su cobertura. Quedan fuera CY, EE, EL,
# FI, LT, LU, MT y SI: no tienen almacenamiento subterráneo, así que AGSI+
# no publica datos suyos (mismo caveat que ALSI con las terminales de GNL).
_CODIGOS_AGSI = {c.value for c in AGSICountry}

# IE (Irlanda) sí está en el enum de gie-py, pero comprobado empíricamente
# AGSI+ solo tiene 25 días de datos suyos en toda su historia, todos de
# abril de 2016 (el almacén de Kinsale Energy dejó de reportarse). La
# excluimos aparte porque el enum no refleja que, en la práctica, nunca hay
# datos para el rango de fechas (2022+) que usa este panel.
_SIN_DATOS_UTILES_AGSI = {'IE'}

NOMBRES_PAISES_AGSI = {
    cod: nombre for cod, nombre in NOMBRES_PAISES_UE.items()
    if cod in _CODIGOS_AGSI and cod not in _SIN_DATOS_UTILES_AGSI
}
NOMBRES_GEO_AGSI = {**NOMBRES_PAISES_AGSI, 'EU': '🇪🇺 Unión Europea (UE-27)'}


def transform_reservas_emergencia(df: "pd.DataFrame") -> "pd.DataFrame":
    """Limpia y transforma el dataset nrg_stk_oem para el panel de días de autonomía.

    Filtra la serie STK_EUE_DIR (stock real en días, unidad NR), convierte a formato
    largo, restringe a países UE-27 y fechas desde 2020.

    Args:
        df: DataFrame crudo devuelto por fetch_reservas_emergencia().

    Returns:
        DataFrame con columnas: geo, Fecha (datetime), Dias (float).
    """
    import pandas as pd

    col_geo = [c for c in df.columns if 'geo' in c.lower()][0]

    df_dias = df[(df['stk_flow'] == 'STK_EUE_DIR') & (df['unit'] == 'NR')].copy()

    fechas = [c for c in df_dias.columns if str(c)[0].isdigit()]

    df_long = df_dias.melt(
        id_vars=[col_geo],
        value_vars=fechas,
        var_name='Fecha',
        value_name='Dias'
    )
    df_long = df_long.rename(columns={col_geo: 'geo'})
    df_long['Fecha'] = pd.to_datetime(df_long['Fecha'], format='%Y-%m')
    df_long = df_long.dropna(subset=['Dias'])
    df_long = df_long[df_long['Fecha'] >= '2020-01-01']
    df_long = df_long[df_long['geo'].isin(NOMBRES_PAISES_UE.keys())]

    return df_long


def transform_origen_gas(df_gas: "pd.DataFrame", geo: str) -> "pd.DataFrame | None":
    """Prepara el pivot de origen de gas para un país o el agregado UE.

    Filtra por geo + gas total (G3000) + unidad TJ_GCV, selecciona top-6 proveedores
    por pico histórico, agrupa el resto en 'Otros proveedores' y pivota a formato wide
    con fechas como índice (desde 2020).

    Para EU27_2020 excluye como proveedores a los propios estados miembro.

    Args:
        df_gas: DataFrame crudo devuelto por fetch_origen_gas()[0].
        geo: código geográfico ('ES', 'DE', 'EU27_2020', ...).

    Returns:
        DataFrame pivotado (fechas × proveedores) o None si no hay datos.
    """
    import pandas as pd

    col_geo = [c for c in df_gas.columns if 'geo' in c.lower()][0]
    fechas = [c for c in df_gas.columns if str(c)[0].isdigit()]

    base = df_gas[
        (df_gas[col_geo] == geo) &
        (df_gas['siec'] == 'G3000') &
        (df_gas['unit'] == 'TJ_GCV')
    ].copy()

    paises = base[base['partner'].str.len() == 2]
    if paises.empty:
        return None

    # Para el agregado UE excluir los estados miembro como "proveedores"
    if geo == 'EU27_2020':
        paises = paises[~paises['partner'].isin(NOMBRES_PAISES_UE.keys())]

    tabla = paises.set_index('partner')[fechas]
    top6 = tabla.max(axis=1).sort_values(ascending=False).head(6).index.tolist()
    grandes = tabla.loc[top6]
    otros = tabla.drop(top6).sum().to_frame().T
    otros.index = ['Otros proveedores']
    apilado = pd.concat([grandes, otros])

    pivot = apilado.T
    pivot.index = pd.to_datetime(pivot.index, format='%Y-%m')
    pivot = pivot.sort_index().fillna(0)
    pivot = pivot[pivot.sum(axis=1) > 0]
    pivot = pivot[pivot.index >= '2020-01-01']

    return pivot


# ── Cobertura de productos petrolíferos ──────────────────────────────────────



def transform_cobertura_us(df_stock_raw, df_supply_raw):
    """Días de cobertura de productos petrolíferos en EEUU.

    US Product Supplied (WDIUPUS2/WKJUPUS2) ya viene en miles bbl/día — es una tasa.
    No se divide por días del mes. Días = stock_kbbl / supply_kbbl_per_día.
    Dividir por días del mes daría un resultado ~30× sobreestimado (bug crítico).
    """
    stock = transform_eia(df_stock_raw)
    supply = transform_eia(df_supply_raw)

    # merge_asof requiere columnas, no índice
    df_s = stock.reset_index().rename(columns={'period': 'fecha', 'value': 'stock'})
    df_d = supply.reset_index().rename(columns={'period': 'fecha', 'value': 'supply'})

    merged = pd.merge_asof(
        df_s.sort_values('fecha'),
        df_d.sort_values('fecha'),
        on='fecha',
        tolerance=pd.Timedelta('7d')
    ).set_index('fecha')

    merged = merged.dropna()
    merged['dias'] = merged['stock'] / merged['supply']
    return merged[['dias']]


# El origen único del metadato. Esta clase se exporta.
class EstadoSPR:
    SIN_DATOS = "sin_datos"
    DRENANDO = "drenando"
    ESTABLE = "estable"

def calcular_autonomias_spr(df: pd.DataFrame, suelo_tecnico: float = 150000.0) -> dict:
    """
    Calcula los días de autonomía restantes del SPR basándose en la ventana real 
    más cercana a 30 días, midiendo la distancia exacta entre puntos temporales.
    """
    if df is None or len(df) < 2:
        return {
            "estado": EstadoSPR.SIN_DATOS,  # Consumo interno formal
            "dias_restantes": None,
            "ultimo_nivel": None,
            "delta_ultimo": 0.0,
            "dias_delta_ultimo": 0,
            "ritmo_diario": 0.0,
            "dias_ventana": 0
        }

    df_sorted = df.copy()
    df_sorted.index = pd.to_datetime(df_sorted.index)
    df_sorted = df_sorted.sort_index()
    
    ultima_fecha = df_sorted.index[-1]
    anterior_fecha = df_sorted.index[-2]
    
    ultimo_nivel = float(df_sorted['value'].iloc[-1])
    nivel_anterior = float(df_sorted['value'].iloc[-2])
    
    delta_ultimo = ultimo_nivel - nivel_anterior
    dias_delta_ultimo = (ultima_fecha - anterior_fecha).days

    fecha_teorica_30d = ultima_fecha - pd.Timedelta(days=30)
    fecha_real_inicio = df_sorted.index.asof(fecha_teorica_30d)
    
    if pd.isna(fecha_real_inicio):
        return {
            "estado": EstadoSPR.SIN_DATOS,
            "dias_restantes": None,
            "ultimo_nivel": ultimo_nivel,
            "delta_ultimo": delta_ultimo,
            "dias_delta_ultimo": dias_delta_ultimo,
            "ritmo_diario": 0.0,
            "dias_ventana": 0
        }
        
    dias_ventana = (ultima_fecha - fecha_real_inicio).days
    
    if dias_ventana <= 0:
        return {
            "estado": EstadoSPR.SIN_DATOS,
            "dias_restantes": None,
            "ultimo_nivel": ultimo_nivel,
            "delta_ultimo": delta_ultimo,
            "dias_delta_ultimo": dias_delta_ultimo,
            "ritmo_diario": 0.0,
            "dias_ventana": 0
        }
        
    nivel_hace_30d = float(df_sorted['value'].loc[fecha_real_inicio])
    media_descenso_diario = (ultimo_nivel - nivel_hace_30d) / float(dias_ventana)
    barriles_disponibles = max(0.0, ultimo_nivel - suelo_tecnico)
    
    if media_descenso_diario < 0:
        estado = EstadoSPR.DRENANDO
        ritmo_vaciado_diario = abs(media_descenso_diario)
        dias_restantes = int(barriles_disponibles / ritmo_vaciado_diario)
    else:
        estado = EstadoSPR.ESTABLE
        dias_restantes = None
        
    return {
        "estado": estado,  # Garantiza que la app reciba la constante controlada
        "dias_restantes": dias_restantes,
        "ultimo_nivel": ultimo_nivel,
        "delta_ultimo": delta_ultimo,
        "dias_delta_ultimo": dias_delta_ultimo,
        "ritmo_diario": media_descenso_diario,
        "dias_ventana": dias_ventana
    }


# ── Grados-día de calefacción (HDD) ──────────────────────────────────────────
#
# Índice propio (pliego «panel-hdd»), no una réplica de Eurostat: fórmula de
# Eurostat aplicada a temperatura diaria de Open-Meteo (ERA5) en 1-3 ciudades
# por país. Solo llevan entrada aquí los países que pasaron la validación de
# la Fase 1 (correlación >= 0,98 y rango de sesgo entre inviernos <= 15
# puntos frente a Eurostat nrg_chdd_m, 2015-16 a 2024-25). Portugal y Suecia
# no pasaron y quedan fuera a propósito — no tienen gráfico en esta versión.
CIUDADES_HDD = {
    'DE': [('Berlín', 52.5200, 13.4050), ('Múnich', 48.1351, 11.5820), ('Hamburgo', 53.5511, 9.9937)],
    'AT': [('Viena', 48.2082, 16.3738), ('Innsbruck', 47.2692, 11.4041)],
    'BG': [('Sofía', 42.6977, 23.3219), ('Varna', 43.2141, 27.9147)],
    'BE': [('Bruselas', 50.8503, 4.3517), ('Amberes', 51.2194, 4.4025)],
    'CZ': [('Praga', 50.0755, 14.4378), ('Brno', 49.1951, 16.6068)],
    'HR': [('Zagreb', 45.8150, 15.9819), ('Split', 43.5081, 16.4402)],
    'DK': [('Copenhague', 55.6761, 12.5683), ('Aarhus', 56.1629, 10.2039)],
    'SK': [('Bratislava', 48.1486, 17.1077), ('Košice', 48.7164, 21.2611)],
    'ES': [('Madrid', 40.4168, -3.7038), ('Barcelona', 41.3874, 2.1686), ('Sevilla', 37.3891, -5.9845)],
    'FR': [('París', 48.8566, 2.3522), ('Marsella', 43.2965, 5.3698), ('Lyon', 45.7640, 4.8357)],
    'HU': [('Budapest', 47.4979, 19.0402), ('Debrecen', 47.5316, 21.6273)],
    'IT': [('Milán', 45.4642, 9.1900), ('Roma', 41.9028, 12.4964), ('Palermo', 38.1157, 13.3615)],
    'LV': [('Riga', 56.9496, 24.1052)],
    'NL': [('Ámsterdam', 52.3676, 4.9041), ('Róterdam', 51.9244, 4.4777)],
    'PL': [('Varsovia', 52.2297, 21.0122), ('Cracovia', 50.0647, 19.9450), ('Gdansk', 54.3520, 18.6466)],
    'RO': [('Bucarest', 44.4268, 26.1025), ('Cluj-Napoca', 46.7712, 23.6236)],
}


def hdd_diario(temperatura_media: pd.Series) -> pd.Series:
    """Grado-día diario, fórmula literal de Eurostat (metadatos `nrg_chdd_esms`):

    si la temperatura media diaria es <= 15°C, el grado-día es 18°C menos esa
    temperatura; si no, 0. Un día sin temperatura (NaN) da NaN, no 0 — sin
    dato no es lo mismo que sin necesidad de calefacción.
    """
    grados = (18.0 - temperatura_media).where(temperatura_media <= 15.0, 0.0)
    return grados.where(temperatura_media.notna())


def _temporada_calefaccion(fecha) -> int:
    """Año de inicio de la temporada (1-oct de ese año a 30-sep del siguiente)."""
    return fecha.year if fecha.month >= 10 else fecha.year - 1


def _dia_desde_1_octubre(fecha) -> int:
    """Días transcurridos desde el 1 de octubre de la temporada de `fecha`."""
    inicio = pd.Timestamp(year=_temporada_calefaccion(fecha), month=10, day=1)
    return (fecha - inicio).days


def transform_hdd(series_ciudades: list) -> pd.DataFrame:
    """HDD diario medio de un país (media de sus 1-3 ciudades) -> acumulado por temporada.

    Args:
        series_ciudades: lista de `pd.Series` de temperatura media diaria (una
            por ciudad del país), indexadas por fecha. Salen de
            `open_meteo_client.fetch_daily_temperature(...)['temperatura']`.

    Returns:
        DataFrame indexado por fecha, columnas: `temporada` (año de inicio),
        `dia_temporada` (días desde el 1-oct de esa temporada) y
        `hdd_acumulado` (acumulado de grados-día dentro de la temporada — se
        reinicia en cada 1 de octubre, un día 30-sep no suma a la temporada
        que empieza al día siguiente).

    Raises:
        ValueError: si `series_ciudades` está vacía, o si hay días sin dato
            (alguna ciudad con NaN) que no sean los últimos de la serie — un
            hueco así es un fallo de la fuente, no una asimetría de fechas
            normal. Los huecos al final (datos aún no publicados) se recortan
            en silencio, no son un error.
    """
    hdd_por_ciudad = [hdd_diario(serie) for serie in series_ciudades]
    # skipna=False a propósito: si falta el dato de una sola ciudad ese día,
    # la media del país para ese día no es fiable — mejor NaN que una media
    # calculada sobre menos ciudades de las pactadas para el país.
    hdd_medio = pd.concat(hdd_por_ciudad, axis=1).mean(axis=1, skipna=False).sort_index()

    ultimo_valido = hdd_medio.last_valid_index()
    if ultimo_valido is None:
        raise ValueError("Ninguna de las ciudades tiene datos: la serie está vacía.")
    hdd_medio = hdd_medio.loc[:ultimo_valido]  # recorta los huecos finales, sin avisar

    huecos = hdd_medio[hdd_medio.isna()]
    if not huecos.empty:
        fechas = ", ".join(f.strftime("%Y-%m-%d") for f in huecos.index)
        raise ValueError(f"Huecos de datos en medio de la serie (no al final): {fechas}")

    df = hdd_medio.to_frame("hdd")
    df["temporada"] = [_temporada_calefaccion(f) for f in df.index]
    df["dia_temporada"] = [_dia_desde_1_octubre(f) for f in df.index]
    df["hdd_acumulado"] = df.groupby("temporada")["hdd"].cumsum()
    return df
