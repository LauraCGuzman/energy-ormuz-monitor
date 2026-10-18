"""Tests del GET común (`data.peticiones.http_get`): timeout y reintentos.

Sin red ni esperas: `requests.get` y `time.sleep` se sustituyen por simulacros.
"""

import unittest
from unittest import mock

import requests

from data import peticiones
from data.peticiones import http_get

URL = "https://api.ejemplo/v1/datos"
CLAVE = "CLAVE_SECRETA_1a2b3c"


def _respuesta(status):
    r = mock.Mock()
    r.status_code = status
    return r


class TestHttpGet(unittest.TestCase):
    def setUp(self):
        parche = mock.patch.object(peticiones.time, "sleep")
        self.sleep = parche.start()
        self.addCleanup(parche.stop)

    def _get(self, **kw):
        parche = mock.patch.object(peticiones.requests, "get", mock.Mock(**kw))
        get = parche.start()
        self.addCleanup(parche.stop)
        return get

    def test_respuesta_buena_un_solo_intento_con_timeout(self):
        ok = _respuesta(200)
        get = self._get(return_value=ok)
        self.assertIs(http_get(URL, {"a": 1}), ok)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.kwargs["timeout"], (10, 60))
        self.assertEqual(get.call_args.kwargs["params"], {"a": 1})
        self.sleep.assert_not_called()

    def test_timeout_y_luego_bien(self):
        ok = _respuesta(200)
        get = self._get(side_effect=[requests.Timeout("t"), ok])
        self.assertIs(http_get(URL), ok)
        self.assertEqual(get.call_count, 2)
        self.sleep.assert_called_once_with(2)

    def test_error_de_conexion_en_todos_los_intentos_se_propaga(self):
        get = self._get(side_effect=requests.ConnectionError("c"))
        with self.assertRaises(requests.ConnectionError):
            http_get(URL)
        self.assertEqual(get.call_count, 3)
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [2, 5])

    def test_5xx_y_429_se_reintentan(self):
        ok = _respuesta(200)
        get = self._get(side_effect=[_respuesta(503), _respuesta(429), ok])
        self.assertIs(http_get(URL), ok)
        self.assertEqual(get.call_count, 3)

    def test_5xx_persistente_devuelve_la_ultima_respuesta(self):
        get = self._get(return_value=_respuesta(502))
        self.assertEqual(http_get(URL).status_code, 502)
        self.assertEqual(get.call_count, 3)

    def test_4xx_no_se_reintenta(self):
        for estado in (400, 403, 404):
            with self.subTest(estado=estado):
                get = self._get(return_value=_respuesta(estado))
                self.assertEqual(http_get(URL).status_code, estado)
                self.assertEqual(get.call_count, 1)

    def test_el_aviso_de_reintento_no_lleva_la_url_ni_el_mensaje(self):
        self._get(side_effect=[requests.Timeout(f"Read timed out. url: {URL}?api_key={CLAVE}"),
                               _respuesta(200)])
        with self.assertLogs(level="WARNING") as logs:
            http_get(f"{URL}?api_key={CLAVE}", etiqueta="EIA WDISTUS1")
        texto = "\n".join(logs.output)
        self.assertIn("EIA WDISTUS1", texto)
        self.assertNotIn(CLAVE, texto)
        self.assertNotIn(URL, texto)


if __name__ == "__main__":
    unittest.main()
