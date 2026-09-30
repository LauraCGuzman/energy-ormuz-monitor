"""Tests de extracción y transformación del panel de diésel EE. UU. → Europa (pliego «Fase 1», PR 2).

Cubre: mes sin fila = 0 solo dentro del rango publicado (después, no hay dato);
suma UE-27 sin GBR, NOR ni el total de EE. UU.; cuota de EE. UU. (vacío, no 0 %);
paginación multiserie con empates en `period`; fechas (viernes EIA, meses
`YYYY-MM` leídos como mes); media de 4 semanas sin efecto de borde; y
`transform_cobertura_us` (semana ausente y supply ≤ 0 → NaN).

Usa `unittest` (stdlib), igual que el resto de la suite del proyecto. Sin red.
"""

import unittest
from unittest import mock

import numpy as np
import pandas as pd
import requests

from data import eia_client
from data.eia_client import (
    _eia_get_paginado, fetch_destilado_exports_destino, PERIMETRO_DESTINOS,
    SERIES_UE27, SERIE_ES, SERIE_GBR, SERIE_NOR, SERIE_EXPORTS_TOTAL_MENSUAL,
)
from data.transform import (
    transform_eia, transform_cobertura_us, transform_exports_destino,
    transform_cuota_us, ultimo_mes_publicado, media_movil_4_semanas,
)

CLAVE = "CLAVE_SECRETA_9f8e7d6c"
URL = "https://api.eia.gov/v2/petroleum/move/expc/data/"
TOTAL = SERIE_EXPORTS_TOTAL_MENSUAL


def _fila(serie, periodo, valor):
    return {"series": serie, "period": periodo, "value": valor}


def _mes(txt):
    return pd.Timestamp(txt)


# ── Exportaciones por destino ─────────────────────────────────────────────────

class TestExportsDestino(unittest.TestCase):
    PERIM = {"UE27": ("A", "B"), "ES": ("B",), "GBR": ("G",), "NOR": ("N",)}

    def _df(self):
        # Meses 2026-01..2026-04; el total llega hasta 2026-03 (último publicado).
        # B (ES) no tiene fila en 2026-02; N (NOR) no tiene ninguna.
        return pd.DataFrame([
            _fila(TOTAL, "2026-01", "100"), _fila(TOTAL, "2026-02", "100"), _fila(TOTAL, "2026-03", "100"),
            _fila("A", "2026-01", "10"), _fila("A", "2026-02", "20"), _fila("A", "2026-03", "30"),
            _fila("A", "2026-04", "999"),  # posterior al último mes publicado
            _fila("B", "2026-01", "1"), _fila("B", "2026-03", "3"),
            _fila("G", "2026-01", "7"),
        ])

    def test_ultimo_mes_publicado_sale_del_total(self):
        self.assertEqual(ultimo_mes_publicado(self._df()), _mes("2026-03-01"))

    def test_mes_sin_fila_dentro_del_rango_es_cero(self):
        r = transform_exports_destino(self._df(), _mes("2026-03-01"), self.PERIM)
        self.assertEqual(r.loc[_mes("2026-02-01"), "ES"], 0.0)   # B sin fila en febrero
        self.assertEqual(r.loc[_mes("2026-02-01"), "GBR"], 0.0)  # G sin fila
        self.assertTrue((r["NOR"] == 0.0).all())                 # N sin ninguna fila

    def test_mes_posterior_al_ultimo_publicado_no_existe(self):
        r = transform_exports_destino(self._df(), _mes("2026-03-01"), self.PERIM)
        self.assertEqual(r.index.max(), _mes("2026-03-01"))
        self.assertNotIn(_mes("2026-04-01"), r.index)  # no es 0 ni 999: no hay dato

    def test_limite_exacto_del_rango(self):
        # El propio último mes publicado sí está y sus valores reales se conservan.
        r = transform_exports_destino(self._df(), _mes("2026-03-01"), self.PERIM)
        self.assertEqual(r.loc[_mes("2026-03-01"), "ES"], 3.0)
        # Con un límite anterior, marzo desaparece.
        r2 = transform_exports_destino(self._df(), _mes("2026-02-01"), self.PERIM)
        self.assertEqual(r2.index.max(), _mes("2026-02-01"))

    def test_la_suma_ue27_no_incluye_gbr_nor_ni_el_total(self):
        r = transform_exports_destino(self._df(), _mes("2026-03-01"), self.PERIM)
        self.assertEqual(r.loc[_mes("2026-01-01"), "UE27"], 11.0)  # A 10 + B 1; ni G 7 ni total 100
        self.assertEqual(r.loc[_mes("2026-02-01"), "UE27"], 20.0)  # A 20 + B ausente (0)
        self.assertEqual(r.loc[_mes("2026-03-01"), "UE27"], 33.0)

    def test_perimetros_reales_no_mezclan_gbr_nor_ni_total(self):
        self.assertNotIn(SERIE_GBR, SERIES_UE27)
        self.assertNotIn(SERIE_NOR, SERIES_UE27)
        self.assertNotIn(TOTAL, SERIES_UE27)
        self.assertIn(SERIE_ES, SERIES_UE27)
        self.assertEqual(len(SERIES_UE27), 27)
        self.assertEqual(len(set(SERIES_UE27)), 27)

    def test_el_total_no_puede_estar_en_un_perimetro(self):
        with self.assertRaises(ValueError):
            transform_exports_destino(self._df(), _mes("2026-03-01"), {"X": (TOTAL, "A")})

    def test_vacio_ante_vacio(self):
        vacio = pd.DataFrame(columns=["series", "period", "value"])
        r = transform_exports_destino(vacio, _mes("2026-03-01"), self.PERIM)
        self.assertTrue(r.empty)
        self.assertEqual(list(r.columns), list(self.PERIM))
        self.assertTrue(transform_exports_destino(self._df(), None, self.PERIM).empty)
        self.assertTrue(transform_exports_destino(None, _mes("2026-03-01"), self.PERIM).empty)
        self.assertIsNone(ultimo_mes_publicado(vacio))
        self.assertIsNone(ultimo_mes_publicado(self._df()[self._df().series != TOTAL]))

    def test_fila_presente_con_valor_nulo_no_es_cero(self):
        df = self._df()
        df.loc[(df.series == "A") & (df.period == "2026-02"), "value"] = None
        r = transform_exports_destino(df, _mes("2026-03-01"), self.PERIM)
        self.assertTrue(np.isnan(r.loc[_mes("2026-02-01"), "UE27"]))
        self.assertEqual(r.loc[_mes("2026-02-01"), "ES"], 0.0)  # sin fila: 0

    def test_ultimo_mes_ignora_un_total_nulo(self):
        df = self._df()
        df.loc[(df.series == TOTAL) & (df.period == "2026-03"), "value"] = None
        self.assertEqual(ultimo_mes_publicado(df), _mes("2026-02-01"))

    def test_los_meses_se_leen_como_mes_no_como_dia(self):
        r = transform_exports_destino(self._df(), _mes("2026-03-01"), self.PERIM)
        self.assertTrue((r.index.day == 1).all())
        self.assertEqual(list(r.index.month), [1, 2, 3])
        self.assertEqual(ultimo_mes_publicado(self._df()).day, 1)
        malo = self._df()
        malo.loc[0, "period"] = "2026-03-05"  # un día no es un mes
        with self.assertRaises(ValueError):
            transform_exports_destino(malo, _mes("2026-03-01"), self.PERIM)

    def test_clave_repetida_lanza(self):
        df = pd.concat([self._df(), pd.DataFrame([_fila("A", "2026-01", "10")])], ignore_index=True)
        with self.assertRaises(ValueError):
            transform_exports_destino(df, _mes("2026-03-01"), self.PERIM)

    def test_perimetro_real_de_la_app(self):
        df = pd.DataFrame([_fila(TOTAL, "2026-01", "50"), _fila(SERIE_ES, "2026-01", "5"),
                           _fila(SERIE_GBR, "2026-01", "8"), _fila(SERIE_NOR, "2026-01", "2")])
        r = transform_exports_destino(df, _mes("2026-01-01"), PERIMETRO_DESTINOS)
        self.assertEqual(r.loc[_mes("2026-01-01")].to_dict(), {"UE27": 5.0, "ES": 5.0, "GBR": 8.0, "NOR": 2.0})


# ── Cuota de EE. UU. en las importaciones (Eurostat) ──────────────────────────

def _eurostat(filas, meses=("2026-05", "2026-06", "2026-07")):
    """DataFrame con la forma de `eurostat.get_data_df`: una fila por (partner, geo)."""
    return pd.DataFrame([
        {"freq": "M", "siec": "O4671", "partner": p, "unit": "THS_T", "geo\\TIME_PERIOD": g,
         **dict(zip(meses, vals))}
        for p, g, vals in filas
    ])


class TestCuotaUS(unittest.TestCase):
    def test_cuota_basica_en_porcentaje(self):
        df = _eurostat([("US", "ES", [10.0, 20.0, 30.0]), ("TOTAL", "ES", [100.0, 100.0, 120.0])])
        c = transform_cuota_us(df)
        self.assertEqual(list(c["ES"]), [10.0, 20.0, 25.0])
        self.assertEqual(list(c.index), [_mes("2026-05-01"), _mes("2026-06-01"), _mes("2026-07-01")])

    def test_denominador_ausente_da_vacio(self):
        df = _eurostat([("US", "ES", [10.0, 20.0, 30.0]), ("TOTAL", "ES", [100.0, None, np.nan])])
        c = transform_cuota_us(df)
        self.assertEqual(c["ES"].iloc[0], 10.0)
        self.assertTrue(np.isnan(c["ES"].iloc[1]))  # None
        self.assertTrue(np.isnan(c["ES"].iloc[2]))  # NaN

    def test_numerador_ausente_da_vacio_no_cero(self):
        df = _eurostat([("US", "ES", [np.nan, None, 30.0]), ("TOTAL", "ES", [100.0, 100.0, 120.0])])
        c = transform_cuota_us(df)
        self.assertTrue(np.isnan(c["ES"].iloc[0]))
        self.assertTrue(np.isnan(c["ES"].iloc[1]))
        self.assertEqual(c["ES"].iloc[2], 25.0)

    def test_fila_de_us_ausente_da_vacio(self):
        df = _eurostat([("TOTAL", "ES", [100.0, 100.0, 120.0])])
        self.assertTrue(transform_cuota_us(df)["ES"].isna().all())

    def test_fila_total_ausente_da_vacio_no_100(self):
        df = _eurostat([("US", "ES", [10.0, 20.0, 30.0])])
        self.assertTrue(transform_cuota_us(df)["ES"].isna().all())

    def test_us_cero_explicito_es_cero_por_ciento(self):
        df = _eurostat([("US", "ES", [0.0, 0.0, 0.0]), ("TOTAL", "ES", [100.0, 100.0, 100.0])])
        self.assertEqual(list(transform_cuota_us(df)["ES"]), [0.0, 0.0, 0.0])

    def test_total_cero_da_vacio(self):
        df = _eurostat([("US", "ES", [0.0, 5.0, 5.0]), ("TOTAL", "ES", [0.0, 0.0, 10.0])])
        c = transform_cuota_us(df)
        self.assertTrue(np.isnan(c["ES"].iloc[0]) and np.isnan(c["ES"].iloc[1]))
        self.assertEqual(c["ES"].iloc[2], 50.0)

    def test_valores_como_texto_o_none_mezclados(self):
        df = _eurostat([("US", "ES", ["10", None, 30.0]), ("TOTAL", "ES", [100.0, "100", None])])
        c = transform_cuota_us(df)
        self.assertEqual(c["ES"].iloc[0], 10.0)
        self.assertTrue(c["ES"].iloc[1:].isna().all())

    def test_dos_geo_con_ultimo_mes_distinto(self):
        # EU27_2020 llega un mes por detrás de ES: NaN en su último mes.
        df = _eurostat([("US", "ES", [10.0, 20.0, 30.0]), ("TOTAL", "ES", [100.0, 100.0, 100.0]),
                        ("US", "EU27_2020", [5.0, 6.0, np.nan]), ("TOTAL", "EU27_2020", [50.0, 60.0, np.nan])])
        c = transform_cuota_us(df)
        self.assertEqual(c["EU27_2020"].iloc[:2].tolist(), [10.0, 10.0])
        self.assertTrue(np.isnan(c["EU27_2020"].iloc[2]))
        self.assertEqual(c["ES"].iloc[2], 30.0)

    def test_los_meses_se_leen_como_mes(self):
        df = _eurostat([("US", "ES", [1.0, 1.0, 1.0]), ("TOTAL", "ES", [10.0, 10.0, 10.0])])
        c = transform_cuota_us(df)
        self.assertTrue((c.index.day == 1).all())
        self.assertEqual(list(c.index.month), [5, 6, 7])

    def test_vacio_ante_vacio(self):
        self.assertTrue(transform_cuota_us(pd.DataFrame()).empty)
        self.assertTrue(transform_cuota_us(None).empty)

    def test_mezclar_productos_lanza(self):
        df = _eurostat([("US", "ES", [1.0, 1.0, 1.0]), ("TOTAL", "ES", [10.0, 10.0, 10.0])])
        df.loc[0, "siec"] = "O46711"
        with self.assertRaises(ValueError):
            transform_cuota_us(df)


# ── Cobertura de EE. UU. ──────────────────────────────────────────────────────

def _semanal(fechas, valores, serie="X"):
    return pd.DataFrame({"period": fechas, "series": serie, "value": [str(v) for v in valores]})


VIERNES = ["2026-08-28", "2026-09-04", "2026-09-11", "2026-09-18"]


class TestCobertura(unittest.TestCase):
    def test_fechas_iguales_mismo_resultado_que_antes(self):
        stock = _semanal(VIERNES, [120000, 121000, 122000, 123000])
        supply = _semanal(VIERNES, [3800, 3900, 4000, 4100])
        # Implementación anterior (merge_asof, tolerancia 7 d) como referencia.
        s = transform_eia(stock).reset_index().rename(columns={"period": "fecha", "value": "stock"})
        d = transform_eia(supply).reset_index().rename(columns={"period": "fecha", "value": "supply"})
        antes = pd.merge_asof(s, d, on="fecha", tolerance=pd.Timedelta("7D")).set_index("fecha").dropna()
        antes["dias"] = antes["stock"] / antes["supply"]
        r = transform_cobertura_us(stock, supply)
        pd.testing.assert_frame_equal(r, antes[["dias"]])

    def test_semana_ausente_en_supply_es_nan_no_la_anterior(self):
        stock = _semanal(VIERNES, [120000, 121000, 122000, 123000])
        supply = _semanal([f for f in VIERNES if f != "2026-09-11"], [3800, 3900, 4100])
        r = transform_cobertura_us(stock, supply)
        self.assertTrue(np.isnan(r.loc["2026-09-11", "dias"]))
        self.assertNotEqual(r.loc["2026-09-11", "dias"], 122000 / 3900)
        self.assertAlmostEqual(r.loc["2026-09-18", "dias"], 123000 / 4100)

    def test_semana_ausente_en_stock_es_nan(self):
        stock = _semanal([f for f in VIERNES if f != "2026-09-04"], [120000, 122000, 123000])
        supply = _semanal(VIERNES, [3800, 3900, 4000, 4100])
        self.assertTrue(np.isnan(transform_cobertura_us(stock, supply).loc["2026-09-04", "dias"]))

    def test_supply_cero_o_negativo_es_nan_no_inf(self):
        stock = _semanal(VIERNES, [120000] * 4)
        supply = _semanal(VIERNES, [3800, 0, -5, 4100])
        r = transform_cobertura_us(stock, supply)["dias"]
        self.assertTrue(np.isnan(r.iloc[1]) and np.isnan(r.iloc[2]))
        self.assertFalse(np.isinf(r).any())

    def test_vacio_ante_vacio(self):
        stock = _semanal(VIERNES, [120000] * 4)
        vacio = pd.DataFrame(columns=["period", "series", "value"])
        self.assertTrue(transform_cobertura_us(stock, vacio).empty)
        self.assertTrue(transform_cobertura_us(vacio, stock).empty)


# ── Fechas semanales y media de 4 semanas ─────────────────────────────────────

class TestSemanal(unittest.TestCase):
    def test_los_periodos_semanales_son_viernes(self):
        df = transform_eia(_semanal(VIERNES, [1, 2, 3, 4]))
        self.assertTrue((df.index.dayofweek == 4).all())  # 4 = viernes

    def test_media_4_semanas_sin_efecto_de_borde(self):
        s = transform_eia(_semanal(VIERNES + ["2026-09-25"], [10, 20, 30, 40, 50]))["value"]
        m = media_movil_4_semanas(s)
        self.assertTrue(m.iloc[:3].isna().all())       # las 3 primeras: NaN
        self.assertEqual(m.iloc[3], 25.0)              # (10+20+30+40)/4
        self.assertEqual(m.iloc[4], 35.0)

    def test_semana_ausente_deja_nan_en_las_ventanas_que_la_contienen(self):
        fechas = ["2026-08-07", "2026-08-14", "2026-08-21", "2026-09-04", "2026-09-11",
                  "2026-09-18", "2026-09-25", "2026-10-02"]  # falta 2026-08-28
        m = media_movil_4_semanas(transform_eia(_semanal(fechas, range(8)))["value"])
        self.assertTrue(np.isnan(m.loc["2026-08-28"]))
        self.assertTrue(m.loc["2026-08-28":"2026-09-18"].isna().all())  # las 4 ventanas con el hueco
        self.assertEqual(m.loc["2026-09-25"], np.mean([3, 4, 5, 6]))     # primera sin el hueco

    def test_fechas_fuera_de_la_rejilla_semanal_lanzan(self):
        s = transform_eia(_semanal(["2026-09-04", "2026-09-11", "2026-09-17"], [1, 2, 3]))["value"]
        with self.assertRaises(ValueError):
            media_movil_4_semanas(s)

    def test_vacio_ante_vacio(self):
        self.assertTrue(media_movil_4_semanas(pd.Series(dtype=float)).empty)


# ── Paginación multiserie ─────────────────────────────────────────────────────

def _pagina(filas, total):
    r = mock.Mock()
    r.status_code = 200
    r.raise_for_status.return_value = None
    r.json.return_value = {"response": {"total": str(total), "data": filas}}
    return r


def _datos_con_empates():
    """6 filas con dos series y el mismo `period` en ambas (empate), ordenadas (series, period)."""
    return [_fila("A", "2026-01", "1"), _fila("A", "2026-02", "2"), _fila("A", "2026-03", "3"),
            _fila("B", "2026-01", "4"), _fila("B", "2026-02", "5"), _fila("B", "2026-03", "6")]


def _get_por_paginas(datos, longitud):
    """Simula la API: sirve `datos` por `offset`/`length` y guarda las peticiones."""
    peticiones = []

    def get(url, params=None, timeout=None):
        peticiones.append(dict(params, timeout=timeout))
        off = params["offset"]
        return _pagina(datos[off:off + longitud], len(datos))
    return get, peticiones


class TestPaginacion(unittest.TestCase):
    def _descargar(self, get, longitud=4):
        with mock.patch.object(eia_client.requests, "get", get):
            return _eia_get_paginado(CLAVE, URL, ("A", "B"), "monthly", "2026-01", longitud=longitud)

    def test_dos_paginas_con_empates_no_duplican_ni_pierden(self):
        datos = _datos_con_empates()
        get, peticiones = _get_por_paginas(datos, longitud=4)
        df = self._descargar(get, longitud=4)
        self.assertEqual(len(peticiones), 2)  # 4 + 2 filas: dos páginas
        self.assertEqual(len(df), 6)
        self.assertFalse(df.duplicated(subset=["series", "period"]).any())
        self.assertEqual(df[["series", "period"]].values.tolist(),
                         [[f["series"], f["period"]] for f in datos])

    def test_la_peticion_ordena_por_series_y_luego_period_y_lleva_timeout(self):
        get, peticiones = _get_por_paginas(_datos_con_empates(), longitud=4)
        self._descargar(get)
        p = peticiones[0]
        self.assertEqual((p["sort[0][column]"], p["sort[1][column]"]), ("series", "period"))
        self.assertEqual(p["facets[series][]"], ["A", "B"])
        self.assertEqual([q["offset"] for q in peticiones], [0, 4])
        self.assertEqual(p["timeout"], (10, 60))

    def test_desorden_de_la_api_por_empates_se_detecta(self):
        # Lo que la Fase 0 midió ordenando solo por `period`: 1 fila duplicada y 1 perdida.
        datos = _datos_con_empates()
        paginas = [datos[0:4], [datos[3]] + datos[5:6]]  # la fila 4 se repite y la 5 no sale
        get = mock.Mock(side_effect=[_pagina(paginas[0], 6), _pagina(paginas[1], 6)])
        with self.assertRaises(RuntimeError):
            self._descargar(get)

    def test_recuento_distinto_de_total_lanza(self):
        datos = _datos_con_empates()
        get = mock.Mock(side_effect=[_pagina(datos[0:4], 7), _pagina(datos[4:6], 7), _pagina([], 7)])
        with self.assertRaisesRegex(RuntimeError, "Recuento"):
            self._descargar(get)

    def test_clave_repetida_lanza(self):
        datos = _datos_con_empates()[:5] + [_fila("A", "2026-01", "1")]
        get, _ = _get_por_paginas(datos, longitud=4)
        with self.assertRaisesRegex(RuntimeError, "repetida"):
            self._descargar(get)

    def test_total_que_cambia_entre_paginas_lanza(self):
        datos = _datos_con_empates()
        get = mock.Mock(side_effect=[_pagina(datos[0:4], 6), _pagina(datos[4:6], 7)])
        with self.assertRaisesRegex(RuntimeError, "total"):
            self._descargar(get)

    def test_respuesta_sin_response_lanza_sin_clave(self):
        r = mock.Mock(); r.raise_for_status.return_value = None; r.json.return_value = {"error": CLAVE}
        with mock.patch.object(eia_client.requests, "get", mock.Mock(return_value=r)):
            with self.assertRaises(RuntimeError) as cm:
                _eia_get_paginado(CLAVE, URL, ("A",), "monthly", "2026-01")
        self.assertNotIn(CLAVE, str(cm.exception))

    def test_los_errores_de_red_no_llevan_la_clave(self):
        e = requests.ConnectionError(f"Max retries exceeded with url: /x?api_key={CLAVE}&f=1")
        with mock.patch.object(eia_client.requests, "get", mock.Mock(side_effect=e)):
            with self.assertRaises(requests.ConnectionError) as cm:
                _eia_get_paginado(CLAVE, URL, ("A",), "monthly", "2026-01")
        self.assertNotIn(CLAVE, str(cm.exception))
        self.assertTrue(cm.exception.__suppress_context__)

    def test_sin_clave_o_sin_series_lanza(self):
        with self.assertRaises(RuntimeError):
            _eia_get_paginado("", URL, ("A",), "monthly", "2026-01")
        with self.assertRaises(ValueError):
            _eia_get_paginado(CLAVE, URL, (), "monthly", "2026-01")

    def test_no_imprime(self):
        import contextlib, io
        salida = io.StringIO()
        get, _ = _get_por_paginas(_datos_con_empates()[:5] + [_fila("A", "2026-01", "1")], 4)
        with contextlib.redirect_stdout(salida), self.assertRaises(RuntimeError):
            self._descargar(get)
        self.assertEqual(salida.getvalue(), "")

    def test_el_wrapper_anade_el_total_como_referencia(self):
        with mock.patch.object(eia_client, "_eia_get_paginado", return_value=pd.DataFrame()) as m:
            fetch_destilado_exports_destino.__wrapped__(CLAVE, (SERIE_ES, SERIE_GBR))
        ids = m.call_args.args[2]
        self.assertEqual(ids, (SERIE_ES, SERIE_GBR, TOTAL))
        with mock.patch.object(eia_client, "_eia_get_paginado", return_value=pd.DataFrame()) as m:
            fetch_destilado_exports_destino.__wrapped__(CLAVE, (SERIE_ES, TOTAL))
        self.assertEqual(m.call_args.args[2], (SERIE_ES, TOTAL))  # sin duplicarlo


if __name__ == "__main__":
    unittest.main()
