"""
Wrapper para el API público de IMF PortWatch.

IMF PortWatch publica datos diarios de tráfico marítimo por chokepoints
(Estrecho de Hormuz, Bab el-Mandeb, Suez, etc.) basándose en señales AIS.

Limitaciones documentadas:
    - GPS jamming en zona del Golfo desde feb-2026.
    - AIS spoofing detectado en buques que evitan ser identificados.
    - El dashboard debe incluir disclaimer explícito sobre estas limitaciones.
"""

from __future__ import annotations
import pandas as pd
import requests
import streamlit as st


PORTWATCH_BASE_URL = "https://portwatch.imf.org"

@st.cache_data(ttl=21600)
def fetch_chokepoint_flows(
    chokepoint: str = "chokepoint6",
    start_year: int = 2024,
    end_year: int | None = None,
) -> pd.DataFrame:
    """Descarga los datos crudos de tráfico marítimo para un chokepoint específico

    manejando de forma iterativa la paginación de la API de ArcGIS del FMI.

    Args:
        chokepoint: Identificador del estrecho (ej. 'chokepoint6' para Hormuz,
          'chokepoint1' para Suez). Por defecto 'chokepoint6'.
        start_year: Año entero de inicio para filtrar el campo 'year'. Por
          defecto 2024.
        end_year: Año entero de fin opcional (inclusive). Si es None, no se pone
          límite superior.

    Returns:
        pd.DataFrame: DataFrame con las 'features' de todas las páginas
        normalizadas conjuntamente, manteniendo los prefijos originales
        'attributes.*'. Sin transformaciones de índice ni nombres de columnas.

    Raises:
        ValueError: Si la API de ArcGIS devuelve un error explícito en alguna
        página. KeyError: Si la respuesta de alguna página no contiene la clave
        'features'.
    """
    url_base = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query"

    # 1. Construcción del WHERE dinámico y estricto
    where_clause = f"portid = '{chokepoint}' AND year >= {start_year}"
    if end_year is not None:
        where_clause += f" AND year <= {end_year}"

    # 2. Preparación para la paginación
    all_features = []
    offset = 0
    page_size = 1000

    params = {
        "where": where_clause,
        "outFields": "*",
        "orderByFields": "date ASC",  # Indispensable para asegurar un orden estable entre páginas
        "f": "json",
        "resultRecordCount": page_size,
        "resultOffset": offset,
    }

    # 3. El bucle de extracción paginada
    while True:
        # Actualizar el desplazamiento para la página actual
        params["resultOffset"] = offset

        response = requests.get(url_base, params=params).json()

        # Validación estricta por cada página obtenida
        if "error" in response:
            raise ValueError(
                f"Error detectado en la API de ArcGIS (offset {offset}): {response['error']}"
            )

        if "features" in response:
            page_features = response["features"]
        else:
            raise KeyError(
                f"Respuesta inesperada en el offset {offset}. Falta la clave 'features'. Respuesta: {response}"
            )

        # Si la página viene vacía, defensa extra para evitar bucles infinitos
        if not page_features:
            break

        # Acumular las filas crudas en la lista principal (.extend añade los elementos, no la lista)
        all_features.extend(page_features)

        # Condición de parada: Si el servidor ya no tiene más datos truncados, terminamos
        if not response.get("exceededTransferLimit", False):
            break

        # Si no paró, avanzamos el offset en función de lo que realmente trajo la página
        offset += len(page_features)

    # 4. Normalización final del conjunto completo acumulado
    df_chokepoint = pd.json_normalize(all_features)

    return df_chokepoint