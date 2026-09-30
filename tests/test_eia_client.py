"""Tests del cliente EIA (pliego «Fase 1», PR 1: seguridad de la clave y timeout).

Comprueba que la clave de la API no sale nunca en el mensaje ni en la traza de
una excepción (HTTPError, ConnectionError, Timeout), que la petición lleva
`timeout` y que una respuesta válida devuelve el mismo DataFrame de siempre.
Sin red: `requests.get` se sustituye por un simulacro.

Usa `unittest` (stdlib), igual que el resto de la suite del proyecto.
"""

import contextlib
import io
import traceback
import unittest
from unittest import mock

import pandas as pd
import requests

from data import eia_client
from data.eia_client import _eia_get, _redactar

CLAVE = "CLAVE_SECRETA_9f8e7d6c"
URL = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"
URL_CON_CLAVE = f"{URL}?api_key={CLAVE}&frequency=weekly"


def _llamar_y_capturar(get_simulado):
    """Ejecuta _eia_get con `get_simulado`; devuelve (excepción, traza, salida stdout)."""
    salida = io.StringIO()
    with mock.patch.object(eia_client.requests, "get", get_simulado), \
            contextlib.redirect_stdout(salida):
        try:
            _eia_get(CLAVE, URL, "WDISTUS1", "weekly", "2023-01-01")
        except Exception as e:  # noqa: BLE001 - se inspecciona la excepción
            return e, traceback.format_exc(), salida.getvalue()
    raise AssertionError("_eia_get no lanzó ninguna excepción")


def _respuesta(status, texto="", json_data=None):
    r = mock.Mock()
    r.status_code = status
    r.text = texto
    r.json.return_value = json_data
    if status != 200:
        r.raise_for_status.side_effect = requests.HTTPError(
            f"{status} Client Error: Forbidden for url: {URL_CON_CLAVE}", response=r)
    return r


class TestClaveNoSale(unittest.TestCase):
    def _assert_sin_clave(self, excepcion, traza, salida):
        self.assertNotIn(CLAVE, str(excepcion))
        self.assertNotIn(CLAVE, traza)
        self.assertNotIn(CLAVE, salida)
        self.assertNotIn(CLAVE, repr(excepcion))

    def test_http_error(self):
        e, traza, salida = _llamar_y_capturar(
            mock.Mock(return_value=_respuesta(403, texto="{}")))
        self.assertIsInstance(e, requests.HTTPError)
        self.assertIn("***", str(e))
        self._assert_sin_clave(e, traza, salida)

    def test_http_error_cuerpo_con_la_clave_no_se_imprime(self):
        # Aunque el cuerpo de la EIA la incluyera, el print del detalle la redacta.
        e, traza, salida = _llamar_y_capturar(mock.Mock(
            return_value=_respuesta(403, texto=f"bad request api_key={CLAVE}")))
        self.assertIn("Detalle:", salida)
        self._assert_sin_clave(e, traza, salida)

    def test_connection_error_estilo_urllib3(self):
        msg = (f"HTTPSConnectionPool(host='api.eia.gov', port=443): Max retries "
               f"exceeded with url: /v2/petroleum/stoc/wstk/data/?api_key={CLAVE}"
               f"&frequency=weekly (Caused by NameResolutionError('boom'))")
        e, traza, salida = _llamar_y_capturar(
            mock.Mock(side_effect=requests.ConnectionError(msg)))
        self.assertIsInstance(e, requests.ConnectionError)
        self._assert_sin_clave(e, traza, salida)

    def test_timeout(self):
        msg = f"Read timed out. url: {URL_CON_CLAVE}"
        e, traza, salida = _llamar_y_capturar(
            mock.Mock(side_effect=requests.Timeout(msg)))
        self.assertIsInstance(e, requests.Timeout)
        self._assert_sin_clave(e, traza, salida)

    def test_la_traza_no_encadena_la_excepcion_original(self):
        # Sin `from None`, la traza incluiría «During handling of the above exception».
        _, traza, _ = _llamar_y_capturar(
            mock.Mock(side_effect=requests.ConnectionError(URL_CON_CLAVE)))
        self.assertNotIn("During handling", traza)
        self.assertNotIn("direct cause", traza)

    def test_clave_codificada_en_url(self):
        clave = "a b&c/d"
        msg = "error url: https://x/?api_key=a+b%26c%2Fd&f=1 y a%20b%26c%2Fd y a b&c/d"
        red = _redactar(msg, clave)
        for fragmento in ("a+b%26c%2Fd", "a%20b%26c%2Fd", "a b&c/d"):
            self.assertNotIn(fragmento, red)

    def test_redactar_sin_clave_no_rompe(self):
        self.assertEqual(_redactar("sin nada", ""), "sin nada")


class TestPeticion(unittest.TestCase):
    def test_la_peticion_lleva_timeout(self):
        get = mock.Mock(return_value=_respuesta(
            200, json_data={"response": {"total": "0", "data": []}}))
        with mock.patch.object(eia_client.requests, "get", get):
            _eia_get(CLAVE, URL, "WDISTUS1", "weekly", "2023-01-01")
        self.assertEqual(get.call_args.kwargs["timeout"], (10, 60))

    def test_respuesta_valida_devuelve_el_mismo_dataframe(self):
        datos = [{"period": "2026-09-18", "series": "WDISTUS1", "value": "123.4"},
                 {"period": "2026-09-25", "series": "WDISTUS1", "value": "125.0"}]
        get = mock.Mock(return_value=_respuesta(
            200, json_data={"response": {"total": "2", "data": datos}}))
        with mock.patch.object(eia_client.requests, "get", get):
            df = _eia_get(CLAVE, URL, "WDISTUS1", "weekly", "2023-01-01")
        pd.testing.assert_frame_equal(df, pd.DataFrame(datos))
        params = get.call_args.kwargs["params"]
        self.assertEqual(params["api_key"], CLAVE)  # la clave sigue yendo a la EIA
        self.assertEqual(params["facets[series][]"], "WDISTUS1")

    def test_sin_clave_lanza_runtimeerror(self):
        with self.assertRaises(RuntimeError):
            _eia_get("", URL, "WDISTUS1", "weekly", "2023-01-01")


if __name__ == "__main__":
    unittest.main()
