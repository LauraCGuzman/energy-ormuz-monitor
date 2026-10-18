"""Tests del cliente de PortWatch: la petición a ArcGIS lleva `timeout`.

Sin `timeout`, un cuelgue de la API deja la página cargando indefinidamente
(no hay excepción que el aislamiento por panel pueda capturar).
Sin red: `requests.get` se sustituye por un simulacro.
"""

import unittest
from unittest import mock

from data import portwatch_client


class TestPeticion(unittest.TestCase):
    def test_la_peticion_lleva_timeout(self):
        respuesta = mock.Mock()
        respuesta.json.return_value = {"features": []}
        get = mock.Mock(return_value=respuesta)
        portwatch_client.fetch_chokepoint_flows.clear()
        with mock.patch.object(portwatch_client.requests, "get", get):
            portwatch_client.fetch_chokepoint_flows("chokepoint6", 2024)
        self.assertEqual(get.call_args.kwargs["timeout"], (10, 60))


if __name__ == "__main__":
    unittest.main()
