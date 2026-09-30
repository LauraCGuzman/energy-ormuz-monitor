"""Tests de los gráficos del panel de diésel EE. UU. → Europa (pliego «Fase 1», PR 2, 2.5).

Cada gráfico dibuja líneas sin apilar y con `connectgaps=False`, y un NaN de la
serie llega a Plotly como NaN (hueco visible), nunca como 0 ni interpolado.

Usa `unittest` (stdlib), igual que el resto de la suite del proyecto.
"""

import unittest

import numpy as np
import pandas as pd

from utils.charts import (
    plot_exports_semanales, plot_cobertura_us, plot_exports_destino, plot_cuota_us,
)


def _semanal():
    return pd.Series([1.0, np.nan, 3.0, 4.0], index=pd.date_range("2026-08-28", periods=4, freq="7D"))


def _mensual(cols):
    idx = pd.date_range("2026-03-01", periods=4, freq="MS")
    return pd.DataFrame({c: [1.0, np.nan, 3.0, 4.0] for c in cols}, index=idx)


class TestChartsDiesel(unittest.TestCase):
    def _comprobar(self, fig, n_trazas):
        self.assertEqual(len(fig.data), n_trazas)
        for t in fig.data:
            self.assertIs(t.connectgaps, False)
            self.assertIsNone(t.stackgroup)
            self.assertIsNone(t.fill)
            self.assertTrue(np.isnan(np.asarray(t.y, dtype=float)[1]))  # el hueco llega como NaN, no 0

    def test_exports_semanales(self):
        self._comprobar(plot_exports_semanales(_semanal(), _semanal()), 2)

    def test_cobertura(self):
        self._comprobar(plot_cobertura_us(_semanal()), 1)

    def test_exports_destino(self):
        nombres = {"UE27": "UE-27", "ES": "España", "GBR": "Reino Unido", "NOR": "Noruega"}
        self._comprobar(plot_exports_destino(_mensual(list(nombres)), nombres), 4)

    def test_cuota(self):
        nombres = {"EU27_2020": "UE-27", "ES": "España"}
        self._comprobar(plot_cuota_us(_mensual(list(nombres)), nombres), 2)

    def test_linea_del_conflicto(self):
        fig = plot_cobertura_us(_semanal())
        self.assertEqual([s.x0 for s in fig.layout.shapes], ["2026-02-28"])


if __name__ == "__main__":
    unittest.main()
