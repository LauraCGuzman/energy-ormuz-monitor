"""Tests del panel de reservas de emergencia por producto (Eurostat nrg_stk_oilm, kt).

Cubre: una sola unidad aunque lleguen varias; regla de huecos del agregado UE-27
(hueco aislado de un miembro anula el mes; NaN permanente y 0 real no); mes ausente =
NaN, nunca 0; `diff()` sobre el índice ordenado; y «UE-27» = `EU27_2020` publicado, no
una suma de países.

Usa `unittest` (stdlib), igual que el resto de la suite del proyecto. Sin red.
"""

import unittest

import numpy as np
import pandas as pd

from data.transform import (
    transform_stocks_producto, huecos_stocks_producto_ue, formatear_huecos_stocks_producto_ue,
    niveles_stocks_producto, variacion_mensual_stocks, formatear_mes_corto,
)

MESES = ["2025-11", "2025-12", "2026-01", "2026-02"]
NAN = np.nan


def _crudo(filas, meses=MESES):
    """Descarga cruda tipo `eurostat.get_data_df`: una fila por (geo, siec, unit)."""
    registros = []
    for geo, siec, valores, *resto in filas:
        unidad = resto[0] if resto else "THS_T"
        registros.append({"freq": "M", "stk_flow": "STKCL_EUE", "siec": siec, "unit": unidad,
                          "geo\\TIME_PERIOD": geo, **dict(zip(meses, valores))})
    return pd.DataFrame(registros)


def _nivel(df, geo, producto):
    largo = transform_stocks_producto(df)
    s = largo[(largo["geo"] == geo) & (largo["producto"] == producto)]
    return s.set_index("Fecha")["kt"]


class TestUnidad(unittest.TestCase):
    def test_filtro_deja_una_sola_unidad(self):
        df = _crudo([("ES", "O4671", [10, 11, 12, 13]),
                     ("ES", "O4671", [900, 900, 900, 900], "MIO_T")])
        largo = transform_stocks_producto(df)
        es = largo[largo["geo"] == "ES"]
        self.assertEqual(es["kt"].tolist(), [10.0, 11.0, 12.0, 13.0])


class TestReglaHuecos(unittest.TestCase):
    def test_hueco_aislado_de_un_miembro_anula_el_mes_del_agregado(self):
        df = _crudo([("ES", "O4671", [10, 11, 12, 13]),
                     ("SE", "O4671", [5, NAN, 5, 5]),
                     ("EU27_2020", "O4671", [15, 11, 17, 18])])
        eu = _nivel(df, "EU27_2020", "gasoleo")
        self.assertTrue(np.isnan(eu["2025-12-01"]))
        self.assertEqual(eu.drop(pd.Timestamp("2025-12-01")).tolist(), [15.0, 17.0, 18.0])  # no se recalcula
        # el miembro conserva su NaN y España no se toca
        self.assertTrue(np.isnan(_nivel(df, "SE", "gasoleo")["2025-12-01"]))
        self.assertEqual(_nivel(df, "ES", "gasoleo").tolist(), [10.0, 11.0, 12.0, 13.0])
        self.assertEqual(huecos_stocks_producto_ue(df),
                         [(pd.Timestamp("2025-12-01"), pd.Timestamp("2025-12-01"), ["Suecia"])])

    def test_nan_permanente_de_un_producto_no_anula_meses(self):
        df = _crudo([("ES", "O4680", [10, 11, 12, 13]),
                     ("SE", "O4680", [NAN, NAN, NAN, NAN]),
                     ("EU27_2020", "O4680", [10, 11, 12, 13])])
        self.assertEqual(_nivel(df, "EU27_2020", "fuel").tolist(), [10.0, 11.0, 12.0, 13.0])
        self.assertEqual(huecos_stocks_producto_ue(df), [])

    def test_nan_de_arranque_o_de_final_no_anula_meses(self):
        df = _crudo([("ES", "O4671", [10, 11, 12, 13]),
                     ("EL", "O4671", [NAN, 5, 5, 5]),     # empieza tarde
                     ("RO", "O4671", [5, 5, 5, NAN]),     # publicación pendiente
                     ("EU27_2020", "O4671", [10, 21, 22, 18])])
        self.assertFalse(_nivel(df, "EU27_2020", "gasoleo").isna().any())
        self.assertEqual(huecos_stocks_producto_ue(df), [])

    def test_cero_real_no_es_hueco(self):
        df = _crudo([("DE", "O4680", [0, 0, 0, 0]),
                     ("ES", "O4680", [10, 11, 12, 13]),
                     ("EU27_2020", "O4680", [10, 11, 12, 13])])
        self.assertEqual(_nivel(df, "EU27_2020", "fuel").tolist(), [10.0, 11.0, 12.0, 13.0])
        self.assertEqual(_nivel(df, "DE", "fuel").tolist(), [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(huecos_stocks_producto_ue(df), [])

    def test_la_regla_es_por_producto(self):
        df = _crudo([("SE", "O4671", [5, NAN, 5, 5]), ("SE", "O4652", [5, 5, 5, 5]),
                     ("EU27_2020", "O4671", [5, 5, 5, 5]), ("EU27_2020", "O4652", [5, 5, 5, 5])])
        self.assertTrue(np.isnan(_nivel(df, "EU27_2020", "gasoleo")["2025-12-01"]))
        self.assertEqual(_nivel(df, "EU27_2020", "gasolina").notna().sum(), 4)

    def test_tramos_consecutivos_se_unen_y_se_formatean(self):
        df = _crudo([("SE", "O4671", [5, NAN, NAN, 5]), ("FR", "O4671", [5, 5, NAN, 5]),
                     ("EU27_2020", "O4671", [10, 5, 5, 10])])
        h = huecos_stocks_producto_ue(df)
        self.assertEqual(h, [(pd.Timestamp("2025-12-01"), pd.Timestamp("2026-01-01"), ["Francia", "Suecia"])])
        self.assertEqual(formatear_huecos_stocks_producto_ue(h), "dic 2025 – ene 2026: Francia, Suecia")
        self.assertEqual(formatear_huecos_stocks_producto_ue(
            [(pd.Timestamp("2025-12-01"), pd.Timestamp("2025-12-01"), ["Suecia"])]), "dic 2025: Suecia")


class TestVariacion(unittest.TestCase):
    def test_mes_ausente_sale_nan_no_cero(self):
        niveles = pd.DataFrame({"gasoleo": [10.0, 12.0, 15.0]},
                               index=pd.to_datetime(["2026-01-01", "2026-02-01", "2026-04-01"]))
        v = variacion_mensual_stocks(niveles)["gasoleo"]
        self.assertEqual(len(v), 4)
        self.assertTrue(np.isnan(v["2026-03-01"]))   # mes sin fila
        self.assertTrue(np.isnan(v["2026-04-01"]))   # el siguiente tampoco inventa un salto
        self.assertEqual(v["2026-02-01"], 2.0)

    def test_diff_con_el_indice_ordenado(self):
        niveles = pd.DataFrame({"gasoleo": [15.0, 10.0, 12.0]},
                               index=pd.to_datetime(["2026-03-01", "2026-01-01", "2026-02-01"]))
        v = variacion_mensual_stocks(niveles)["gasoleo"]
        self.assertEqual(v.index.tolist(), sorted(v.index.tolist()))
        self.assertTrue(np.isnan(v.iloc[0]))
        self.assertEqual(v.iloc[1:].tolist(), [2.0, 3.0])


class TestAgregadoUE(unittest.TestCase):
    def test_ue27_usa_eu27_2020_y_no_suma_paises(self):
        # El agregado publicado (999) difiere a propósito de la suma de países (21).
        df = _crudo([("ES", "O4671", [10, 10, 10, 10]), ("FR", "O4671", [11, 11, 11, 11]),
                     ("EU27_2020", "O4671", [999, 999, 999, 999])])
        n = niveles_stocks_producto(transform_stocks_producto(df), "EU27_2020")
        self.assertEqual(n["gasoleo"].tolist(), [999.0] * 4)

    def test_meses_vacios_de_los_extremos_se_quitan_y_los_internos_se_conservan(self):
        meses = ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02"]
        df = _crudo([("EU27_2020", "O4671", [NAN, 5, NAN, 7, NAN])], meses=meses)
        n = niveles_stocks_producto(transform_stocks_producto(df), "EU27_2020")
        self.assertEqual(n.index.tolist(), list(pd.to_datetime(["2025-11-01", "2025-12-01", "2026-01-01"])))
        self.assertTrue(np.isnan(n["gasoleo"].iloc[1]))


class TestFormatoMes(unittest.TestCase):
    def test_mes_corto_en_espanol_sin_depender_del_locale(self):
        self.assertEqual(formatear_mes_corto(pd.Timestamp("2026-06-01")), "jun 2026")
        self.assertEqual(formatear_mes_corto(pd.Timestamp("2025-12-15")), "dic 2025")


if __name__ == "__main__":
    unittest.main()
