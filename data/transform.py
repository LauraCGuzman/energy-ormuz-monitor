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


def transform_lng(data):
    # 1. Copiar para evitar mutación
    df = data.copy()

    # 2. Eliminar gasDayEnd por redundancia (el índice ya es gasDayStart)
    df.drop(columns=["gasDayEnd"], errors="ignore", inplace=True)

    # 3. Columnnas año y dia del año
    df["año"] = df.index.year
    df["dia_del_año"] = df.index.dayofyear
    # Nota: Los numéricos ya vienen como float/int y 'status' se mantiene como str.
    return df