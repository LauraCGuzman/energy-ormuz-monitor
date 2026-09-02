"""Tests de `data.gie_client.fetch_gas_storage`: manejo de `NoMatchingDataError`.

«País sin datos» y «datos rotos» son dos fallos distintos (ver
`app.py::panel_reservas_eu_gas`). Este módulo solo cubre el primero, en la
capa de datos: `fetch_gas_storage` debe convertir `NoMatchingDataError` —y
solo esa excepción— en un DataFrame vacío, dejando cualquier otra (timeout,
red, autenticación) propagarse sin tocar.

El caso de la columna `full` ausente vive en `panel_reservas_eu_gas`
(app.py), que no es testeable sin arrancar Streamlit de verdad
(`st.selectbox`, `st.secrets`, `st.error` necesitan un script run real) —
no se fuerza un test artificial para eso; se verificó a mano (ver PR).
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
