"""Tests de la guarda del sendOut de GNL (pliego «fix-pico-gnl-alsi»).

`data.transform.sendout_gnl_validado` va entre `fetch_lng` y `media_7d_atras`
en el panel de entrada de gas a la UE. Origen: el 5/10/2026 la terminal de
Ravenna publicó 100.000 GWh/d en ALSI+ y el GNL del panel saltó a ~18.000
GWh/d durante una semana.
"""

import unittest

import numpy as np
import pandas as pd

from data.transform import (
    formatear_dias_excluidos_gnl,
    media_7d_atras,
    sendout_gnl_validado,
    triaje_sendout_gnl,
)


def _df_alsi(n=60, sendout=3600.0, dtrs=8000.0, inicio="2026-08-10"):
    """DataFrame con forma ALSI+ (sendOut, dtrs), índice ascendente."""
    fechas = pd.date_range(inicio, periods=n, freq="D", name="gasDayStart")
    return pd.DataFrame({"sendOut": [sendout] * n, "dtrs": [dtrs] * n, "status": "C"}, index=fechas)


class TestDiaAnomalo(unittest.TestCase):
    def test_dia_por_20_se_excluye_y_se_registra(self):
        df = _df_alsi()
        dia = df.index[50]
        df.loc[dia, "sendOut"] = 3600.0 * 20  # 72.000: sobre dtrs y sobre 2× mediana

        with self.assertLogs(level="WARNING") as log:
            sendout, excluidos = sendout_gnl_validado(df, pais="EU")

        self.assertTrue(np.isnan(sendout[dia]))
        self.assertEqual(list(excluidos.index), [dia])
        self.assertEqual(excluidos[dia], 72000.0)
        self.assertEqual(len(log.output), 1)
        self.assertIn(dia.strftime("%Y-%m-%d"), log.output[0])
        self.assertIn("72000.0", log.output[0])
        # La media de 7 días sigue en el nivel normal, sin hueco.
        media = media_7d_atras(sendout)
        self.assertTrue((media.iloc[6:] == 3600.0).all())

    def test_solo_sobre_mediana_tambien_se_excluye(self):
        # Por debajo de dtrs pero más del doble de la mediana de los 30 días previos.
        df = _df_alsi(dtrs=10000.0)
        dia = df.index[40]
        df.loc[dia, "sendOut"] = 7500.0
        sospechoso = triaje_sendout_gnl(df["sendOut"], df["dtrs"])
        self.assertEqual(list(df.index[sospechoso]), [dia])

    def test_serie_normal_no_registra_nada(self):
        df = _df_alsi()
        df["sendOut"] = 3600.0 + 400.0 * np.sin(np.arange(len(df)))
        with self.assertNoLogs(level="WARNING"):
            sendout, excluidos = sendout_gnl_validado(df)
        self.assertTrue(excluidos.empty)
        self.assertFalse(sendout.isna().any())

    def test_formato_del_aviso(self):
        excluidos = pd.Series([103636.8], index=pd.DatetimeIndex(["2026-10-05"]))
        self.assertEqual(formatear_dias_excluidos_gnl(excluidos), "5 oct 2026 (103.637 GWh/d)")


class TestIndice(unittest.TestCase):
    def test_fecha_duplicada_falla_explicitamente(self):
        df = _df_alsi(n=10)
        df = pd.concat([df, df.iloc[[3]]])
        with self.assertRaisesRegex(ValueError, "repetida.*2026-08-13"):
            sendout_gnl_validado(df)

    def test_indice_descendente_se_ordena_antes_del_rolling(self):
        df = _df_alsi(n=10)
        df["sendOut"] = np.arange(1.0, 11.0) * 100  # 100, 200, ..., 1000 en orden cronológico
        df["dtrs"] = 5000.0
        descendente = df.iloc[::-1]  # como lo devuelve GIE
        self.assertTrue(descendente.index.is_monotonic_decreasing)

        sendout, _ = sendout_gnl_validado(descendente)

        self.assertTrue(sendout.index.is_monotonic_increasing)
        media = media_7d_atras(sendout)
        # Día 7 cronológico: media de 100..700 = 400 (con el índice al revés saldría otra cosa).
        self.assertEqual(media.iloc[6], 400.0)
        self.assertEqual(media.iloc[-1], 700.0)


if __name__ == "__main__":
    unittest.main()
