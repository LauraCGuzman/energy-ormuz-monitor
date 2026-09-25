"""Tests de `utils.charts.plot_entrada_gas_ue` (pliego «huecos-panel-entrada-gas»).

Usa `unittest` (stdlib), igual que el resto de la suite del proyecto.

Cubre justo lo que falló antes: un día "incompleto" (algún origen sin dato)
NO debe llegar a Plotly como un punto apilable — ni como 0, ni interpolado.
Ver el docstring de `plot_entrada_gas_ue` y de
`data.transform.vaciar_dia_si_falta_algun_origen` para la cita de
`plotly.js` (`scatter/calc`) que explica por qué `px.area` con
`stackgaps='infer zero'` no basta.

Las fechas y orígenes de un hueco NO se dibujan como texto sobre la banda
(se solapan si hay varias seguidas): van en el caption del panel, generados
por `data.transform.huecos_entrada_gas_ue` +
`data.transform.formatear_huecos_entrada_gas_ue` — la misma lista que se le
pasa a `plot_entrada_gas_ue` para las bandas, así que ambos tests parten de
esa función, no de texto escrito a mano.
"""

import unittest

import numpy as np
import pandas as pd

from data.transform import huecos_entrada_gas_ue, formatear_huecos_entrada_gas_ue
from utils.charts import plot_entrada_gas_ue


def _df_con_hueco_interno():
    fechas = pd.date_range("2026-01-01", periods=10, freq="D")
    df = pd.DataFrame(
        {"GNL": [10.0] * 10, "Argelia": [20.0] * 10},
        index=fechas,
    )
    dia_incompleto = fechas[4]
    df.loc[dia_incompleto, "Argelia"] = np.nan
    return df, dia_incompleto


def _bandas_de_hueco(fig):
    """Shapes de `fig` que son bandas de hueco (`add_vrect`, gris) — excluye
    la línea vertical fija del inicio del conflicto (`add_vline`), que
    también es un shape pero no tiene nada que ver con los huecos.
    """
    return [s for s in fig.layout.shapes if s.fillcolor == "lightgray"]


def _df_con_dos_huecos_internos():
    """3 tramos completos separados por 2 huecos, con Argelia presente en
    los tres tramos — para comprobar que comparte `legendgroup` entre ellos.
    """
    fechas = pd.date_range("2026-01-01", periods=20, freq="D")
    df = pd.DataFrame(
        {"GNL": [10.0] * 20, "Argelia": [20.0] * 20},
        index=fechas,
    )
    df.loc[fechas[4], "Argelia"] = np.nan
    df.loc[fechas[12]:fechas[13], "Argelia"] = np.nan
    return df


class TestDiaIncompletoNoLlegaApilable(unittest.TestCase):
    def test_la_fecha_incompleta_no_aparece_en_ninguna_traza(self):
        df, dia_incompleto = _df_con_hueco_interno()
        fig = plot_entrada_gas_ue(df, huecos_entrada_gas_ue(df))

        for trace in fig.data:
            fechas_trace = pd.to_datetime(pd.Index(trace.x))
            self.assertNotIn(
                dia_incompleto, fechas_trace,
                f"el día incompleto {dia_incompleto.date()} llegó al eje x de "
                f"la traza {trace.name!r} — Plotly lo apilará como 0 "
                "(stackgaps='infer zero')"
            )

    def test_ningun_valor_apilado_es_nan_donde_deberia_haber_hueco(self):
        # Si por error se pasara el DataFrame sin recortar (con NaN en vez
        # de ausente), este test lo detectaría igual: un NaN en `y` con la
        # fecha presente en `x` es exactamente lo que Plotly apila como 0.
        df, _ = _df_con_hueco_interno()
        fig = plot_entrada_gas_ue(df, huecos_entrada_gas_ue(df))
        for trace in fig.data:
            self.assertFalse(any(pd.isna(v) for v in trace.y))

    def test_dias_completos_antes_y_despues_del_hueco_se_conservan(self):
        df, dia_incompleto = _df_con_hueco_interno()
        fig = plot_entrada_gas_ue(df, huecos_entrada_gas_ue(df))
        todas_las_fechas = set()
        for trace in fig.data:
            todas_las_fechas.update(pd.to_datetime(pd.Index(trace.x)))
        esperadas = set(df.index) - {dia_incompleto}
        self.assertEqual(todas_las_fechas, esperadas)

    def test_un_hueco_final_sin_tramo_completo_despues_no_se_dibuja(self):
        fechas = pd.date_range("2026-01-01", periods=10, freq="D")
        df = pd.DataFrame(
            {"GNL": [10.0] * 10, "Argelia": [20.0] * 10},
            index=fechas,
        )
        df.loc[fechas[-3]:, "Argelia"] = np.nan
        huecos = huecos_entrada_gas_ue(df)
        self.assertEqual(huecos, [])  # el tramo final no cuenta como hueco

        fig = plot_entrada_gas_ue(df, huecos)
        todas_las_fechas = set()
        for trace in fig.data:
            todas_las_fechas.update(pd.to_datetime(pd.Index(trace.x)))
        self.assertEqual(todas_las_fechas, set(fechas[:-3]))
        self.assertEqual(_bandas_de_hueco(fig), [])


class TestBandasSinTexto(unittest.TestCase):
    """Las bandas grises marcan el hueco pero no llevan texto encima — el
    texto va en el caption (`formatear_huecos_entrada_gas_ue`), no aquí.
    """

    def test_la_banda_no_lleva_texto_de_origen(self):
        df, _ = _df_con_hueco_interno()
        fig = plot_entrada_gas_ue(df, huecos_entrada_gas_ue(df))
        textos_annot = [a.text for a in fig.layout.annotations]
        self.assertFalse(
            any("Argelia" in (t or "") for t in textos_annot),
            f"la banda no debería llevar el nombre del origen: {textos_annot}"
        )
        self.assertFalse(any("Sin dato completo" in (t or "") for t in textos_annot))

    def test_la_banda_gris_esta_en_las_fechas_del_hueco(self):
        df, dia_incompleto = _df_con_hueco_interno()
        huecos = huecos_entrada_gas_ue(df)
        fig = plot_entrada_gas_ue(df, huecos)
        bandas = _bandas_de_hueco(fig)
        self.assertEqual(len(bandas), 1)
        banda = bandas[0]
        self.assertEqual(pd.Timestamp(banda.x0), dia_incompleto)
        self.assertEqual(pd.Timestamp(banda.x1), dia_incompleto)


class TestCaptionEnumeraHuecosDesdeLosMismosDatos(unittest.TestCase):
    """El texto del caption (`panel_entrada_gas_ue` en app.py) sale de
    `formatear_huecos_entrada_gas_ue(huecos_entrada_gas_ue(df))` — la MISMA
    lista que dibuja las bandas, nunca escrito a mano.
    """

    def test_un_hueco_de_un_dia_se_formatea_con_fecha_corta_y_origen(self):
        df, dia_incompleto = _df_con_hueco_interno()
        huecos = huecos_entrada_gas_ue(df)
        texto = formatear_huecos_entrada_gas_ue(huecos)
        self.assertEqual(texto, "5 ene 2026: Argelia")

    def test_un_hueco_de_varios_dias_dentro_del_mismo_mes(self):
        fechas = pd.date_range("2025-06-01", periods=20, freq="D")
        df = pd.DataFrame(
            {"GNL": [10.0] * 20, "Rusia": [5.0] * 20},
            index=fechas,
        )
        df.loc["2025-06-13":"2025-06-18", "Rusia"] = np.nan
        huecos = huecos_entrada_gas_ue(df)
        texto = formatear_huecos_entrada_gas_ue(huecos)
        self.assertEqual(texto, "13–18 jun 2025: Rusia")

    def test_varios_huecos_se_unen_con_punto_y_coma(self):
        df = _df_con_dos_huecos_internos()
        huecos = huecos_entrada_gas_ue(df)
        texto = formatear_huecos_entrada_gas_ue(huecos)
        self.assertEqual(texto, "5 ene 2026: Argelia; 13–14 ene 2026: Argelia")

    def test_un_origen_con_parentesis_propios_no_se_anida_en_otro_parentesis(self):
        fechas = pd.date_range("2026-03-01", periods=15, freq="D")
        df = pd.DataFrame(
            {"GNL": [10.0] * 15, "Reino Unido (mixto)": [5.0] * 15},
            index=fechas,
        )
        df.loc["2026-03-08":"2026-03-11", "Reino Unido (mixto)"] = np.nan
        huecos = huecos_entrada_gas_ue(df)
        texto = formatear_huecos_entrada_gas_ue(huecos)
        self.assertEqual(texto, "8–11 mar 2026: Reino Unido (mixto)")

    def test_sin_huecos_da_texto_vacio(self):
        self.assertEqual(formatear_huecos_entrada_gas_ue([]), "")


class TestLegendgroupCompartidoEntreTramos(unittest.TestCase):
    """Ocultar un origen en la leyenda debe ocultarlo en TODOS los tramos —
    para eso todas sus trazas, en cualquier tramo, deben compartir el mismo
    `legendgroup` (Plotly agrupa el toggle de visibilidad por ese campo).
    """

    def test_todas_las_trazas_de_un_origen_comparten_legendgroup(self):
        df = _df_con_dos_huecos_internos()
        huecos = huecos_entrada_gas_ue(df)
        self.assertEqual(len(huecos), 2, "el fixture debe producir 3 tramos")
        fig = plot_entrada_gas_ue(df, huecos)

        trazas_argelia = [t for t in fig.data if t.name == "Argelia"]
        self.assertEqual(len(trazas_argelia), 3, "una traza de Argelia por tramo")
        legendgroups = {t.legendgroup for t in trazas_argelia}
        self.assertEqual(
            legendgroups, {"Argelia"},
            f"todas las trazas de Argelia deberían compartir legendgroup, hay: {legendgroups}"
        )

    def test_solo_el_primer_tramo_muestra_la_entrada_en_la_leyenda(self):
        df = _df_con_dos_huecos_internos()
        fig = plot_entrada_gas_ue(df, huecos_entrada_gas_ue(df))
        trazas_argelia = [t for t in fig.data if t.name == "Argelia"]
        mostradas = [bool(t.showlegend) for t in trazas_argelia]
        self.assertEqual(mostradas, [True, False, False])


if __name__ == "__main__":
    unittest.main()
