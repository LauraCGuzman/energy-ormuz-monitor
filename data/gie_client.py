"""
Wrapper sobre la librería `gie-py` para consultar AGSI+ y ALSI+.

AGSI+ : reservas de gas subterráneo en Europa (datos diarios desde 2011).
ALSI+ : utilización de terminales LNG en Europa (datos diarios desde 2012).

Ambos endpoints comparten la misma API key, que se obtiene gratis registrándose
en https://agsi.gie.eu.

Decisiones de diseño:
    - Las funciones devuelven `pandas.DataFrame` ya tipados y con índice temporal.
    - El cliente se crea una vez por sesión (cacheable con `st.cache_resource`).
    - Los errores de red o de API se propagan al caller; el dashboard decide
      cómo presentarlos al usuario.
"""

from __future__ import annotations

import pandas as pd


# TODO: importar GiePandasClient cuando se implemente
# from gie import GiePandasClient


def get_client(api_key: str):
    """Crea un cliente GIE autenticado.

    Args:
        api_key: clave personal de GIE (registro gratuito en agsi.gie.eu).

    Returns:
        Instancia de `GiePandasClient` lista para consultar AGSI+ y ALSI+.
    """
    raise NotImplementedError


def fetch_gas_storage(
    client,
    country: str = "ES",
    start: str = "2022-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Consulta AGSI+ — nivel de llenado de reservas de gas subterráneo.

    Args:
        client: cliente GIE autenticado.
        country: código ISO-2 del país (por defecto España).
        start: fecha de inicio (YYYY-MM-DD).
        end: fecha de fin (None = hasta hoy).

    Returns:
        DataFrame con columnas: gasInStorage, full (%), trend, injection, withdrawal.
        Índice: fecha (datetime).
    """
    raise NotImplementedError


def fetch_lng_terminals(
    client,
    country: str = "ES",
    start: str = "2022-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Consulta ALSI+ — utilización de terminales LNG.

    Args:
        client: cliente GIE autenticado.
        country: código ISO-2 del país (por defecto España, 6 terminales).
        start: fecha de inicio (YYYY-MM-DD).
        end: fecha de fin (None = hasta hoy).

    Returns:
        DataFrame con columnas: dtmi (capacidad), sendout (gas a red), inventory.
        Índice: fecha (datetime).
    """
    raise NotImplementedError
