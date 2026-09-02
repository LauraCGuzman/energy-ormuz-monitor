"""Tests de `data.gie_client.fetch_gas_storage`: manejo de `NoMatchingDataError`.

Tres estados distintos en `panel_reservas_eu_gas` (app.py), cada uno con su
propio mensaje: (1) país sin datos — `NoMatchingDataError`, `st.warning`;
(2) columna `full` ausente — esquema roto, `st.error`; (3) `full` presente
pero íntegramente NaN — dato inservible, `st.error` distinto del anterior.
Un NaN parcial en `full` NO es ninguno de los tres: es `_capa_vecinos`
funcionando como toca, y no lleva aviso.

Este módulo solo cubre el (1), en la capa de datos: `fetch_gas_storage` debe
convertir `NoMatchingDataError` —y solo esa excepción— en un DataFrame
vacío, dejando cualquier otra (timeout, red, autenticación) propagarse sin
tocar.

Los casos (2) y (3) viven enteros dentro de `panel_reservas_eu_gas`
(app.py), que no es testeable sin arrancar Streamlit de verdad
(`st.selectbox`, `st.secrets`, `st.error` necesitan un script run real, y
mockear cada llamada de Streamlit para llegar a un `if` sería un test
artificial, no una verificación) — se verificaron a mano (ver PR).
"""

import unittest

import pandas as pd
from gie.exceptions import NoMatchingDataError

from data.gie_client import fetch_gas_storage
from data.transform import transform_gas


class _ClienteSimulado:
    """Cliente GIE falso: no toca red, solo lanza la excepción que interesa."""

    def __init__(self, excepcion):
        self._excepcion = excepcion

    def query_gas_country(self, country, start, end):
        raise self._excepcion


class TestFetchGasStorage(unittest.TestCase):
    def test_devuelve_dataframe_vacio_si_no_matching_data(self):
        cliente = _ClienteSimulado(NoMatchingDataError())
        with self.assertLogs(level="WARNING") as cm:
            resultado = fetch_gas_storage(
                cliente, country="XX", start="2022-01-01", end="2022-01-02"
            )

        self.assertTrue(resultado.empty)
        self.assertIn(
            "[gie/gas_storage] XX: sin datos en AGSI+ para 2022-01-01..2022-01-02",
            cm.output[0],
        )

        # Regresión: el DataFrame vacío tiene que llevar un DatetimeIndex, no
        # el RangeIndex por defecto de pd.DataFrame() — si no, transform_gas
        # revienta en df.index.year en vez de devolver un df vacío limpio.
        self.assertIsInstance(resultado.index, pd.DatetimeIndex)
        transformado = transform_gas(resultado, pais="XX")
        self.assertTrue(transformado.empty)

    def test_no_captura_una_excepcion_distinta(self):
        # Timeouts, red o autenticación son bugs o caídas, no ausencia de
        # datos: no se silencian, se propagan tal cual.
        cliente = _ClienteSimulado(ConnectionError("red caída"))
        with self.assertRaises(ConnectionError):
            fetch_gas_storage(
                cliente, country="YY", start="2022-01-01", end="2022-01-02"
            )


if __name__ == "__main__":
    unittest.main()
