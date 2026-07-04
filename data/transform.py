import pandas as pd


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


def transform_gas(data):
    # 1. Copiar para evitar mutación
    df = data.copy()

    # 2. Eliminar gasDayEnd por redundancia (el índice ya es gasDayStart)
    df.drop(columns=["gasDayEnd"], errors="ignore", inplace=True)

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