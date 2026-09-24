"""Tests de las funciones puras del índice de grados-día (pliego «panel-hdd»).

Cubre la fórmula literal de Eurostat (metadatos `nrg_chdd_esms`) en sus
ejemplos y en los bordes del umbral de 15°C, que un día sin temperatura da
NaN y no 0, el acumulado por temporada (1-oct a 30-sep, un 30-sep no debe
sumar a la temporada que empieza al día siguiente), y que un hueco de datos
se trata distinto según esté al final de la serie (se recorta) o en medio
(revienta con `ValueError`).

Usa `unittest` (stdlib), igual que el resto de la suite del proyecto.
"""

import unittest

import pandas as pd

from data.transform import hdd_diario, transform_hdd


class TestHddDiario(unittest.TestCase):
    def test_ejemplos_y_bordes_de_eurostat(self):
        # 12->6 y 16->0 son los dos ejemplos literales de la metadata de
        # Eurostat; 15/15.1/-5 son los bordes del umbral (<=15 vs >15).
        temperaturas = pd.Series([12.0, 16.0, 15.0, 15.1, -5.0])
        esperado = pd.Series([6.0, 0.0, 3.0, 0.0, 23.0])

        resultado = hdd_diario(temperaturas)

        pd.testing.assert_series_equal(resultado, esperado, check_names=False)

    def test_temperatura_vacia_da_resultado_vacio(self):
        # Sin dato no es lo mismo que "no hace falta calefacción" (0): tiene
        # que seguir siendo NaN, no colarse como un 0 en la media del país.
        temperaturas = pd.Series([12.0, None, 16.0])

        resultado = hdd_diario(temperaturas)

        self.assertEqual(resultado.iloc[0], 6.0)
        self.assertTrue(pd.isna(resultado.iloc[1]))
        self.assertEqual(resultado.iloc[2], 0.0)


class TestTransformHdd(unittest.TestCase):
    def test_30_septiembre_no_suma_a_la_temporada_siguiente(self):
        fechas = pd.DatetimeIndex(["2024-09-30", "2024-10-01"])
        temperaturas = pd.Series([10.0, 5.0], index=fechas)  # HDD: 8.0 y 13.0

        resultado = transform_hdd([temperaturas])

        # Si el 30-sep sumara a la temporada que empieza el 1-oct, el
        # acumulado del 1-oct sería 21.0 (8+13) en vez de 13.0.
        self.assertEqual(resultado.loc["2024-09-30", "hdd_acumulado"], 8.0)
        self.assertEqual(resultado.loc["2024-10-01", "hdd_acumulado"], 13.0)

    def test_30_sep_y_1_oct_quedan_en_temporadas_distintas(self):
        fechas = pd.DatetimeIndex(["2024-09-30", "2024-10-01"])
        temperaturas = pd.Series([10.0, 5.0], index=fechas)

        resultado = transform_hdd([temperaturas])

        self.assertNotEqual(
            resultado.loc["2024-09-30", "temporada"],
            resultado.loc["2024-10-01", "temporada"],
        )

    def test_media_entre_varias_ciudades_del_pais(self):
        fechas = pd.DatetimeIndex(["2024-10-01"])
        ciudad_a = pd.Series([5.0], index=fechas)   # HDD 13.0
        ciudad_b = pd.Series([15.0], index=fechas)  # HDD 3.0

        resultado = transform_hdd([ciudad_a, ciudad_b])

        self.assertEqual(resultado.loc["2024-10-01", "hdd_acumulado"], 8.0)  # media(13, 3)

    def test_dias_vacios_al_final_se_recortan(self):
        fechas = pd.DatetimeIndex(["2024-10-01", "2024-10-02", "2024-10-03"])
        # El 10-03 falta en las dos ciudades: hueco al final, se descarta sin avisar.
        ciudad_a = pd.Series([5.0, 5.0, None], index=fechas)
        ciudad_b = pd.Series([5.0, 5.0, None], index=fechas)

        resultado = transform_hdd([ciudad_a, ciudad_b])

        self.assertEqual(len(resultado), 2)
        self.assertNotIn(pd.Timestamp("2024-10-03"), resultado.index)

    def test_hueco_en_medio_lanza_value_error(self):
        fechas = pd.DatetimeIndex(["2024-10-01", "2024-10-02", "2024-10-03"])
        # Falta el 10-02, pero el 10-03 sí tiene dato: el hueco no está al
        # final de la serie, así que no se puede recortar en silencio.
        ciudad_a = pd.Series([5.0, None, 5.0], index=fechas)

        with self.assertRaises(ValueError):
            transform_hdd([ciudad_a])


if __name__ == "__main__":
    unittest.main()
