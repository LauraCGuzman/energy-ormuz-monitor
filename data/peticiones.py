"""Petición GET común a las fuentes REST (EIA, PortWatch, ENTSOG, Open-Meteo).

Un único criterio de timeout y reintentos para todas: las APIs públicas a
veces dejan una petición colgada o responden 429/5xx de forma pasajera, y la
siguiente petición sale bien. GIE y Eurostat no pasan por aquí: van por
librería y su red no la controlamos.

Sigue llamando a `requests.get`, así que los tests que lo sustituyen por un
simulacro funcionan igual. Los avisos de reintento no llevan la URL ni el
mensaje de la excepción: en la EIA ambos incluyen la clave de la API.
"""
from __future__ import annotations

import logging
import time

import requests

TIMEOUT = (10, 60)  # (conexión, lectura) en segundos
INTENTOS = 3
ESPERAS = (2, 5)  # segundos antes del 2.º y del 3.er intento
ESTADOS_REINTENTABLES = frozenset({429, 500, 502, 503, 504})


def http_get(url: str, params=None, *, etiqueta: str = "petición",
             intentos: int = INTENTOS) -> requests.Response:
    """GET con timeout y reintentos ante fallos pasajeros.

    Reintenta ante `requests.Timeout`, `requests.ConnectionError` y los estados
    de `ESTADOS_REINTENTABLES`. Un 4xx distinto de 429 no se reintenta: no se
    arregla repitiendo la petición.

    Returns:
        La respuesta tal cual, también si el último intento devuelve un estado
        de error: cada cliente decide qué hacer con ella (`raise_for_status`,
        tratar el 404 como «sin datos», etc.).

    Raises:
        requests.Timeout | requests.ConnectionError: si fallan todos los intentos,
        la excepción del último, sin tocar (el cliente la redacta si hace falta).
    """
    for intento in range(1, intentos + 1):
        ultimo = intento == intentos
        try:
            respuesta = requests.get(url, params=params, timeout=TIMEOUT)
        except (requests.Timeout, requests.ConnectionError) as e:
            if ultimo:
                raise
            motivo = type(e).__name__
        else:
            if ultimo or respuesta.status_code not in ESTADOS_REINTENTABLES:
                return respuesta
            motivo = f"estado {respuesta.status_code}"
        espera = ESPERAS[min(intento - 1, len(ESPERAS) - 1)]
        logging.warning("%s: %s, reintento %d de %d en %d s",
                        etiqueta, motivo, intento, intentos - 1, espera)
        time.sleep(espera)
