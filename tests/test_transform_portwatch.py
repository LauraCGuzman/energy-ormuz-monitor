"""Tests de `data.transform.transform_portwatch` y del diccionario de chokepoints.

Cubre el pliego «selector-chokepoints»: el conjunto de opciones del selector
sale de un único diccionario (`NOMBRES_CHOKEPOINTS`), `transform_portwatch`
sigue descartando `portid`/`portname` por ser constantes en un fetch
mono-chokepoint (decisión del 19/6, sin tocar por este PR), y el rótulo del
panel se construye desde el `portid` solicitado — nunca desde una columna del
DataFrame que ya no existe tras el transform.

Usa `unittest` (stdlib), igual que `tests/test_transform_gas.py`: la suite del
proyecto no introduce `pytest` sin decisión explícita.

La construcción de `chokepoint_id` a partir de `st.selectbox` vive entera
dentro de `panel_portwatch` (app.py), que no es testeable sin arrancar
Streamlit de verdad (mismo motivo documentado en
`tests/test_gie_client.py` para `panel_reservas_eu_gas`) — se verificó a mano
contra el fixture de `sandbox/` (ver informe de Fase 0 / PR).
"""

import unittest

import pandas as pd

from data.transform import (
    CHOKEPOINT_DEFECTO,
    NOMBRES_CHOKEPOINTS,
    etiqueta_chokepoint,
    transform_portwatch,
)


def _df_portwatch_crudo(fechas, portid="chokepoint6", portname="Strait of Hormuz"):
    """DataFrame con la forma cruda real de `fetch_chokepoint_flows`:

    prefijo `attributes.*`, columnas constantes de un fetch mono-chokepoint
    (`portid`, `portname`) y artefactos de paginación (`ObjectId`, `year`,
    `month`, `day`). Columnas verificadas contra el fixture real de
    `sandbox/fixture_portwatch_hormuz.parquet` (informe de Fase 0).
    """
    n = len(fechas)
    return pd.DataFrame(
        {
            "attributes.date": fechas,
            "attributes.year": [2025] * n,
            "attributes.month": [1] * n,
            "attributes.day": list(range(1, n + 1)),
            "attributes.portid": [portid] * n,
            "attributes.portname": [portname] * n,
            "attributes.n_tanker": [float(i) for i in range(n)],
            "attributes.n_total": [float(i) * 2 for i in range(n)],
            "attributes.ObjectId": list(range(1, n + 1)),
        }
    )


class TestNombresChokepoints(unittest.TestCase):
    def test_seis_entradas(self):
        self.assertEqual(len(NOMBRES_CHOKEPOINTS), 6)

    def test_sin_portid_repetido(self):
        # Las claves de un dict ya son únicas por construcción; el test
        # deja explícita esa garantía frente a un futuro refactor a listas
        # paralelas (lección del selector de gas, log del 1/9).
        self.assertEqual(len(NOMBRES_CHOKEPOINTS), len(set(NOMBRES_CHOKEPOINTS.keys())))

    def test_defecto_es_ormuz(self):
        self.assertEqual(CHOKEPOINT_DEFECTO, "chokepoint6")
        self.assertIn(CHOKEPOINT_DEFECTO, NOMBRES_CHOKEPOINTS)


class TestTransformPortwatch(unittest.TestCase):
    def test_indice_datetime_ordenado(self):
        # Fechas deliberadamente desordenadas para comprobar el sort_index.
        crudo = _df_portwatch_crudo(["2025-01-03", "2025-01-01", "2025-01-02"])
        limpio = transform_portwatch(crudo)

        self.assertIsInstance(limpio.index, pd.DatetimeIndex)
        self.assertTrue(limpio.index.is_monotonic_increasing)

    def test_descarta_columnas_constantes(self):
        crudo = _df_portwatch_crudo(["2025-01-01", "2025-01-02"])
        limpio = transform_portwatch(crudo)

        self.assertNotIn("portid", limpio.columns)
        self.assertNotIn("portname", limpio.columns)


class TestEtiquetaChokepoint(unittest.TestCase):
    def test_rotulo_desde_portid_no_desde_dataframe(self):
        # Pura por diseño: no recibe el DataFrame transformado, solo el
        # identificador solicitado (ver docstring de `etiqueta_chokepoint`).
        self.assertEqual(etiqueta_chokepoint("chokepoint6"), "Estrecho de Ormuz")
        self.assertEqual(etiqueta_chokepoint("chokepoint1"), "Canal de Suez")

    def test_id_desconocido_devuelve_el_propio_id(self):
        self.assertEqual(etiqueta_chokepoint("chokepoint99"), "chokepoint99")


if __name__ == "__main__":
    unittest.main()
