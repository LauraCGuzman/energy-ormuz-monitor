"""Tests de las capas de calidad de `data.transform.transform_gas`.

Cubren el refactor de consolidación (pliego «refactor-calidad-gas»): las dos
capas —capacidad y vecinos— deben actuar en orden fijo, avisar por log solo
cuando actúan, y no-opear en silencio sobre datos con forma ALSI (GNL), que
no tienen las columnas de ninguna de las dos.

Es la primera suite de tests del proyecto: usa `unittest` (stdlib) para no
introducir una dependencia nueva (`pytest`) sin decisión explícita.
"""

import unittest

import pandas as pd

from data.transform import (
    _calidad_gas,
    _capa_capacidad,
    _capa_vecinos,
    _formatear_fechas,
    transform_gas,
)


def _df_agsi(fechas, working_gas_volume, gas_in_storage, full):
    """DataFrame con forma AGSI (índice ya ordenado cronológicamente)."""
    return pd.DataFrame(
        {
            "gasInStorage": gas_in_storage,
            "workingGasVolume": working_gas_volume,
            "full": full,
        },
        index=pd.DatetimeIndex(fechas, name="gasDayStart"),
    )


class TestFormatearFechas(unittest.TestCase):
    def test_hasta_cinco_fechas_se_listan_completas(self):
        idx = pd.DatetimeIndex(["2023-01-01", "2023-01-02"])
        self.assertEqual(_formatear_fechas(idx), "2023-01-01, 2023-01-02")

    def test_mas_de_cinco_trunca_a_las_tres_primeras_mas_el_total(self):
        # Comparación de string completo: separador ASCII ("...", no "…")
        # por el mismo motivo que el "-" de los avisos.
        idx = pd.DatetimeIndex(pd.date_range("2023-01-01", periods=7))
        self.assertEqual(
            _formatear_fechas(idx),
            "2023-01-01, 2023-01-02, 2023-01-03, ... (7 en total)",
        )


class TestCapaCapacidad(unittest.TestCase):
    def test_descarta_fila_con_capacidad_cero_o_nan(self):
        df = _df_agsi(
            ["2023-01-01", "2023-01-02", "2023-01-03"],
            working_gas_volume=[10.0, 0.0, float("nan")],
            gas_in_storage=[5.0, 5.0, 5.0],
            full=[50.0, 50.0, 50.0],
        )
        with self.assertLogs(level="WARNING") as cm:
            resultado = _capa_capacidad(df, "SE")

        self.assertEqual(
            list(resultado.index.strftime("%Y-%m-%d")), ["2023-01-01"]
        )
        # Comparación de string completo: fija el separador ASCII ("-", no
        # "—") para que el mensaje no se rompa en la consola de Windows.
        self.assertEqual(
            cm.output[0],
            "WARNING:root:[calidad_gas/capacidad] SE: 2 filas descartadas "
            "por workingGasVolume<=0 o NaN - 2023-01-02, 2023-01-03",
        )

    def test_no_opera_ni_avisa_sin_columna_de_capacidad(self):
        # Forma ALSI: sin workingGasVolume.
        df = pd.DataFrame(
            {"lngInventory": [1.0, 2.0], "full": [10.0, 20.0]},
            index=pd.DatetimeIndex(["2023-01-01", "2023-01-02"]),
        )
        with self.assertNoLogs(level="WARNING"):
            resultado = _capa_capacidad(df, "EU")
        pd.testing.assert_frame_equal(resultado, df)


class TestCapaVecinos(unittest.TestCase):
    def test_anula_full_en_dia_con_vecinos_identicos_y_stock_lejano(self):
        # Día 2: los vecinos (día 1 y día 3) coinciden EXACTAMENTE entre sí,
        # y el día 2 se aleja más de un 20% de ellos.
        df = _df_agsi(
            ["2023-01-01", "2023-01-02", "2023-01-03"],
            working_gas_volume=[10.0, 10.0, 10.0],
            gas_in_storage=[100.0, 130.0, 100.0],
            full=[50.0, 55.0, 50.0],
        )
        with self.assertLogs(level="WARNING") as cm:
            resultado = _capa_vecinos(df, "SE")

        self.assertEqual(len(resultado), 3)  # la fila NO se descarta
        self.assertTrue(pd.isna(resultado.loc["2023-01-02", "full"]))
        self.assertEqual(resultado.loc["2023-01-01", "full"], 50.0)
        self.assertEqual(resultado.loc["2023-01-03", "full"], 50.0)
        # Comparación de string completo: fija el separador ASCII ("-", no
        # "—") para que el mensaje no se rompa en la consola de Windows.
        self.assertEqual(
            cm.output[0],
            "WARNING:root:[calidad_gas/vecinos] SE: 1 valor de 'full' "
            "anulado por stock anómalo - 2023-01-02",
        )

    def test_no_opera_ni_avisa_sin_columnas_de_vecinos(self):
        # Forma ALSI: sin gasInStorage (tiene lngInventory) y sin full.
        df = pd.DataFrame(
            {"lngInventory": [1.0, 2.0], "sendOut": [1.0, 2.0]},
            index=pd.DatetimeIndex(["2023-01-01", "2023-01-02"]),
        )
        with self.assertNoLogs(level="WARNING"):
            resultado = _capa_vecinos(df, "EU")
        pd.testing.assert_frame_equal(resultado, df)


class TestCalidadGasCombinada(unittest.TestCase):
    """Fija el comportamiento del §5 del pliego: capacidad cero → fila fuera;
    día con dato bueno y stock anómalo → fila dentro con `full` nulo."""

    def test_orden_fijo_capacidad_luego_vecinos(self):
        # d2 (2023-02-28): capacidad 0 → se descarta.
        # d4 (2023-03-02): stock anómalo respecto a d3/d5 → full se anula,
        # la fila se queda. d3 y d5 son idénticos entre sí a propósito.
        df = _df_agsi(
            ["2023-02-27", "2023-02-28", "2023-03-01", "2023-03-02", "2023-03-03"],
            working_gas_volume=[10.0, 0.0, 10.0, 10.0, 10.0],
            gas_in_storage=[100.0, 100.0, 110.0, 140.0, 110.0],
            full=[50.0, 50.0, 52.0, 53.0, 52.0],
        )

        resultado = _calidad_gas(df, "SE")

        self.assertEqual(
            list(resultado.index.strftime("%Y-%m-%d")),
            ["2023-02-27", "2023-03-01", "2023-03-02", "2023-03-03"],
        )
        self.assertTrue(pd.isna(resultado.loc["2023-03-02", "full"]))
        self.assertEqual(resultado.loc["2023-03-01", "full"], 52.0)
        self.assertEqual(resultado.loc["2023-03-03", "full"], 52.0)


class TestTransformGasFormaAlsi(unittest.TestCase):
    """El caso que detectaría un cambio de esquema de GIE: sin
    `workingGasVolume` ni `gasInStorage`, `transform_gas` no debe tocar nada
    salvo añadir las columnas de calendario."""

    def test_passthrough_para_forma_alsi(self):
        fechas = pd.DatetimeIndex(
            ["2023-01-01", "2023-01-02", "2023-01-03"], name="gasDayStart"
        )
        df_bruto = pd.DataFrame(
            {
                "lngInventory": [10.0, 12.0, 11.0],
                "sendOut": [1.0, 2.0, 1.5],
                "full": [40.0, 48.0, 44.0],
                "status": ["C", "C", "C"],
            },
            index=fechas,
        )

        with self.assertNoLogs(level="WARNING"):
            resultado = transform_gas(df_bruto.copy(), pais="EU")

        columnas_originales = ["lngInventory", "sendOut", "full", "status"]
        pd.testing.assert_frame_equal(
            resultado[columnas_originales], df_bruto[columnas_originales]
        )
        self.assertEqual(
            set(resultado.columns) - set(columnas_originales),
            {"año", "fecha_normalizada"},
        )


if __name__ == "__main__":
    unittest.main()
