"""Tests de las funciones puras de entrada de gas a la UE (pliego «panel-gasoductos»).

Cubre la regla de calidad (las cuatro filas de la tabla del pliego, Fase
2.3), la conversión kWh/d -> GWh/d, la suma por origen (dos puntos del mismo
origen se suman; si uno está vacío, el origen-día queda vacío), la media
móvil de 7 días (no usa días futuros; con el cambio de la PARADA 3 exige al
menos 5 de los 7 días, no los 7) y la sincronización de vacíos entre
orígenes para el gráfico (un origen vacío vacía la fila entera, para que
Plotly no la rellene con 0 vía `stackgaps='infer zero'`). También comprueba
que el mapa de puntos incluidos no contiene ningún punto de los marcados
como excluidos, ni en `PUNTOS_REENTRADA_EXCLUIDOS` ni en
`PUNTOS_SIN_DATOS_PUBLICADOS`.

Usa `unittest` (stdlib), igual que el resto de la suite del proyecto.
"""

import unittest

import pandas as pd

from data.transform import (
    regla_calidad_entsog, kwh_dia_a_gwh_dia, sumar_por_origen, media_7d_atras,
    contar_dias_sospechosos, vaciar_dia_si_falta_algun_origen, _ensamblar_largo,
)
from data.entsog_client import (
    MAPA_PUNTOS_ENTRADA, PUNTOS_REENTRADA_EXCLUIDOS, PUNTOS_SIN_DATOS_PUBLICADOS,
    PuntoEntrada, _requiere_cobertura_completa, _es_respuesta_truncada_por_limite,
    _cobertura_incompleta,
)


class TestReglaCalidadEntsog(unittest.TestCase):
    def test_las_cuatro_filas_de_la_tabla(self):
        flujo = pd.Series([0.0, 0.0, float("nan"), 5.0])
        nominacion = pd.Series([0.0, 3.0, 1.0, 1.0])

        resultado = regla_calidad_entsog(flujo, nominacion)

        self.assertEqual(resultado.iloc[0], 0.0)          # 0 físico, 0 nominado -> 0 (parada real)
        self.assertTrue(pd.isna(resultado.iloc[1]))        # 0 físico, >0 nominado -> vacío (sospechoso)
        self.assertTrue(pd.isna(resultado.iloc[2]))        # vacío físico -> vacío, sea cual sea la nominación
        self.assertEqual(resultado.iloc[3], 5.0)           # >0 físico -> el flujo, sea cual sea la nominación

    def test_con_flujo_contrario_positivo_es_cero_real(self):
        # 0 físico + nominación > 0, pero ese día hay flujo de SALIDA > 0 en
        # el mismo punto: el gas fluyó al revés, el 0 de entrada es real.
        flujo = pd.Series([0.0])
        nominacion = pd.Series([5.0])
        flujo_salida = pd.Series([100.0])

        resultado = regla_calidad_entsog(flujo, nominacion, flujo_salida)

        self.assertEqual(resultado.iloc[0], 0.0)

    def test_sin_flujo_contrario_sigue_vacio(self):
        # Mismo caso sospechoso, pero sin flujo de salida ese día (0): no se
        # rescata, sigue vacío.
        flujo = pd.Series([0.0])
        nominacion = pd.Series([5.0])
        flujo_salida = pd.Series([0.0])

        resultado = regla_calidad_entsog(flujo, nominacion, flujo_salida)

        self.assertTrue(pd.isna(resultado.iloc[0]))


class TestConversionKwhAGwh(unittest.TestCase):
    def test_un_millon_kwh_dia_es_un_gwh_dia(self):
        resultado = kwh_dia_a_gwh_dia(pd.Series([1_000_000.0]))

        self.assertEqual(resultado.iloc[0], 1.0)

    def test_nan_se_mantiene_nan(self):
        resultado = kwh_dia_a_gwh_dia(pd.Series([float("nan")]))

        self.assertTrue(pd.isna(resultado.iloc[0]))


class TestSumarPorOrigen(unittest.TestCase):
    def test_dos_puntos_del_mismo_origen_se_suman(self):
        df_largo = pd.DataFrame({
            "fecha": ["2025-01-01", "2025-01-01"],
            "origen": ["Noruega", "Noruega"],
            "valor_gwh": [10.0, 5.0],
        })

        resultado = sumar_por_origen(df_largo)

        self.assertEqual(resultado.loc["2025-01-01", "Noruega"], 15.0)

    def test_un_punto_vacio_deja_el_origen_dia_vacio(self):
        df_largo = pd.DataFrame({
            "fecha": ["2025-01-01", "2025-01-01"],
            "origen": ["Noruega", "Noruega"],
            "valor_gwh": [10.0, float("nan")],
        })

        resultado = sumar_por_origen(df_largo)

        self.assertTrue(pd.isna(resultado.loc["2025-01-01", "Noruega"]))

    def test_origenes_distintos_no_se_mezclan(self):
        df_largo = pd.DataFrame({
            "fecha": ["2025-01-01", "2025-01-01"],
            "origen": ["Noruega", "Argelia"],
            "valor_gwh": [10.0, float("nan")],
        })

        resultado = sumar_por_origen(df_largo)

        # Argelia vacío ese día no debe contaminar a Noruega.
        self.assertEqual(resultado.loc["2025-01-01", "Noruega"], 10.0)
        self.assertTrue(pd.isna(resultado.loc["2025-01-01", "Argelia"]))


class TestMedia7dAtras(unittest.TestCase):
    def _serie_diaria(self, valores):
        fechas = pd.date_range("2025-01-01", periods=len(valores), freq="D")
        return pd.Series(valores, index=fechas)

    def test_no_usa_dias_futuros(self):
        # Un salto grande el último día no debe afectar a la media de días anteriores.
        serie = self._serie_diaria([1.0] * 10 + [1000.0])

        resultado = media_7d_atras(serie)

        # El día 10 (índice 9, antes del salto) es la media de los días 4-10: todo 1.0.
        self.assertEqual(resultado.iloc[9], 1.0)

    def test_vacia_si_faltan_mas_de_2_de_los_7(self):
        # Ventana de 7 días con solo 4 datos (faltan 3): por debajo del mínimo de 5.
        valores = [1.0, 1.0, 1.0, 1.0, float("nan"), float("nan"), float("nan")]
        serie = self._serie_diaria(valores)

        resultado = media_7d_atras(serie)

        self.assertTrue(pd.isna(resultado.iloc[6]))

    def test_media_de_los_disponibles_con_exactamente_5_de_los_7(self):
        # Faltan 2 de los 7: se promedian los 5 que hay, no se imputan los que faltan.
        valores = [10.0, 10.0, 10.0, 10.0, 10.0, float("nan"), float("nan")]
        serie = self._serie_diaria(valores)

        resultado = media_7d_atras(serie)

        self.assertEqual(resultado.iloc[6], 10.0)

    def test_media_correcta_con_los_7_dias_completos(self):
        serie = self._serie_diaria([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])

        resultado = media_7d_atras(serie)

        self.assertEqual(resultado.iloc[6], 4.0)  # media(1..7)
        self.assertTrue(pd.isna(resultado.iloc[3]))  # solo 4 días disponibles, por debajo del mínimo de 5


class TestVaciarDiaSiFaltaAlgunOrigen(unittest.TestCase):
    def test_un_origen_vacio_vacia_toda_la_fila(self):
        df = pd.DataFrame({
            "Noruega": [1.0, 2.0],
            "Argelia": [5.0, float("nan")],
        })

        resultado = vaciar_dia_si_falta_algun_origen(df)

        self.assertEqual(resultado.loc[0, "Noruega"], 1.0)
        self.assertEqual(resultado.loc[0, "Argelia"], 5.0)
        self.assertTrue(pd.isna(resultado.loc[1, "Noruega"]))  # vaciado pese a tener dato
        self.assertTrue(pd.isna(resultado.loc[1, "Argelia"]))

    def test_fila_completa_no_se_toca(self):
        df = pd.DataFrame({"Noruega": [1.0], "Argelia": [5.0]})

        resultado = vaciar_dia_si_falta_algun_origen(df)

        self.assertEqual(resultado.loc[0, "Noruega"], 1.0)
        self.assertEqual(resultado.loc[0, "Argelia"], 5.0)


class TestContarDiasSospechosos(unittest.TestCase):
    def test_cuenta_dias_de_calendario_no_combinaciones_origen_dia(self):
        # Dos orígenes DISTINTOS sospechosos el MISMO día: el aviso dice
        # «días», así que cuenta 1 día, no 2 combinaciones origen-día.
        fechas = pd.date_range("2025-01-01", periods=1, freq="D")
        mapa = [
            PuntoEntrada("PTO-A", "OP-A", "Punto A", "Noruega"),
            PuntoEntrada("PTO-B", "OP-B", "Punto B", "Argelia"),
        ]
        datos_flujo = {
            ("PTO-A", "OP-A"): pd.Series([0.0], index=fechas),
            ("PTO-B", "OP-B"): pd.Series([0.0], index=fechas),
        }
        datos_nominacion = {
            ("PTO-A", "OP-A"): pd.Series([3.0], index=fechas),
            ("PTO-B", "OP-B"): pd.Series([7.0], index=fechas),
        }

        n = contar_dias_sospechosos(datos_flujo, datos_nominacion, mapa)

        self.assertEqual(n, 1)

    def test_dias_de_calendario_distintos_se_cuentan_por_separado(self):
        fechas = pd.date_range("2025-01-01", periods=2, freq="D")
        mapa = [PuntoEntrada("PTO-A", "OP-A", "Punto A", "Noruega")]
        datos_flujo = {("PTO-A", "OP-A"): pd.Series([0.0, 0.0], index=fechas)}
        datos_nominacion = {("PTO-A", "OP-A"): pd.Series([3.0, 4.0], index=fechas)}

        n = contar_dias_sospechosos(datos_flujo, datos_nominacion, mapa)

        self.assertEqual(n, 2)


class TestAgrupacionPorPuntoFisico(unittest.TestCase):
    def test_operador_en_0_compensado_por_otro_no_deja_el_punto_vacio(self):
        # Dos operadores del MISMO punto físico (grupo_fisico compartido):
        # A cae a 0 con nominación (sospechoso si se mirara solo), pero B
        # compensa al alza. El total del punto (500) no es 0, así que ni
        # siquiera entra en la regla de sospechoso — no queda vacío.
        fechas = pd.date_range("2025-01-01", periods=1, freq="D")
        mapa = [
            PuntoEntrada("PTO-A", "OP-A", "Operador A", "Noruega", grupo_fisico="Punto X"),
            PuntoEntrada("PTO-B", "OP-B", "Operador B", "Noruega", grupo_fisico="Punto X"),
        ]
        datos_flujo = {
            ("PTO-A", "OP-A"): pd.Series([0.0], index=fechas),
            ("PTO-B", "OP-B"): pd.Series([500.0], index=fechas),
        }
        datos_nominacion = {
            ("PTO-A", "OP-A"): pd.Series([300.0], index=fechas),
            ("PTO-B", "OP-B"): pd.Series([500.0], index=fechas),
        }

        df_largo = _ensamblar_largo(datos_flujo, datos_nominacion, mapa)

        self.assertEqual(len(df_largo), 1)  # un solo grupo, no dos filas
        self.assertFalse(bool(df_largo["sospechoso"].iloc[0]))
        self.assertFalse(pd.isna(df_largo["valor_gwh"].iloc[0]))
        self.assertAlmostEqual(df_largo["valor_gwh"].iloc[0], 500.0 / 1_000_000)

    def test_sin_grupo_fisico_cada_punto_es_su_propio_grupo(self):
        # Comportamiento previo intacto para los puntos sin grupo_fisico
        # compartido: cada uno se evalúa por su cuenta.
        fechas = pd.date_range("2025-01-01", periods=1, freq="D")
        mapa = [
            PuntoEntrada("PTO-A", "OP-A", "Punto A", "Noruega"),
            PuntoEntrada("PTO-B", "OP-B", "Punto B", "Argelia"),
        ]
        datos_flujo = {
            ("PTO-A", "OP-A"): pd.Series([0.0], index=fechas),
            ("PTO-B", "OP-B"): pd.Series([10.0], index=fechas),
        }
        datos_nominacion = {
            ("PTO-A", "OP-A"): pd.Series([5.0], index=fechas),  # sospechoso, sin quien lo compense
            ("PTO-B", "OP-B"): pd.Series([10.0], index=fechas),
        }

        df_largo = _ensamblar_largo(datos_flujo, datos_nominacion, mapa)

        self.assertEqual(len(df_largo), 2)
        fila_a = df_largo[df_largo["origen"] == "Noruega"].iloc[0]
        self.assertTrue(bool(fila_a["sospechoso"]))
        self.assertTrue(pd.isna(fila_a["valor_gwh"]))


class TestMapaPuntosEntrada(unittest.TestCase):
    def test_ningun_punto_excluido_aparece_en_el_mapa_de_inclusion(self):
        incluidos = {punto.point_key for punto in MAPA_PUNTOS_ENTRADA}
        excluidos_reentrada = {point_key for point_key, _motivo in PUNTOS_REENTRADA_EXCLUIDOS}
        excluidos_sin_datos = {punto.point_key for punto in PUNTOS_SIN_DATOS_PUBLICADOS}

        self.assertEqual(incluidos & excluidos_reentrada, set())
        self.assertEqual(incluidos & excluidos_sin_datos, set())

    def test_todas_las_exclusiones_tienen_motivo(self):
        for point_key, motivo in PUNTOS_REENTRADA_EXCLUIDOS:
            self.assertTrue(point_key)
            self.assertTrue(motivo)

    def test_todos_los_puntos_sin_datos_tienen_motivo_y_fecha(self):
        for punto in PUNTOS_SIN_DATOS_PUBLICADOS:
            self.assertTrue(punto.point_key)
            self.assertTrue(punto.motivo)
            self.assertTrue(punto.fecha_ultimo_dato)


class TestRequiereCoberturaCompleta(unittest.TestCase):
    def test_solo_flujo_fisico_de_entrada_la_exige(self):
        self.assertTrue(_requiere_cobertura_completa("Physical Flow", "entry"))

    def test_nominacion_no_la_exige_aunque_sea_entry(self):
        self.assertFalse(_requiere_cobertura_completa("Nomination", "entry"))

    def test_flujo_de_salida_no_la_exige(self):
        self.assertFalse(_requiere_cobertura_completa("Physical Flow", "exit"))


class TestEsRespuestaTruncadaPorLimite(unittest.TestCase):
    def test_con_exactamente_el_limite_de_filas(self):
        serie = pd.Series(range(2000), index=pd.date_range("2025-01-01", periods=2000))

        self.assertTrue(_es_respuesta_truncada_por_limite(serie, limit=2000))

    def test_con_menos_filas_que_el_limite_no_es_truncada(self):
        serie = pd.Series(range(10), index=pd.date_range("2025-01-01", periods=10))

        self.assertFalse(_es_respuesta_truncada_por_limite(serie, limit=2000))


class TestCoberturaIncompleta(unittest.TestCase):
    def test_respuesta_completa_pasa(self):
        serie = pd.Series(
            range(10), index=pd.date_range("2025-01-01", "2025-01-10")
        )

        self.assertFalse(_cobertura_incompleta(serie, "2025-01-01", "2025-01-10"))

    def test_respuesta_que_empieza_tarde_da_error(self):
        # Pedido desde 2025-01-01, pero el primer dato es del 2025-01-06:
        # 5 días de retraso, más de los 3 de margen.
        serie = pd.Series(
            range(5), index=pd.date_range("2025-01-06", "2025-01-10")
        )

        self.assertTrue(_cobertura_incompleta(serie, "2025-01-01", "2025-01-10"))

    def test_respuesta_que_acaba_pronto_da_error(self):
        # Pedido hasta 2025-01-10, pero el último dato es del 2025-01-05:
        # 5 días antes del fin, más de los 3 de margen.
        serie = pd.Series(
            range(5), index=pd.date_range("2025-01-01", "2025-01-05")
        )

        self.assertTrue(_cobertura_incompleta(serie, "2025-01-01", "2025-01-10"))

    def test_respuesta_vacia_de_flujo_fisico_de_entrada_da_error(self):
        serie = pd.Series(dtype="float64", index=pd.DatetimeIndex([]))

        self.assertTrue(_cobertura_incompleta(serie, "2025-01-01", "2025-01-10"))

    def test_margen_de_3_dias_pasa(self):
        # Retraso/adelanto de exactamente 3 días: dentro del margen, no es error.
        serie = pd.Series(
            range(4), index=pd.date_range("2025-01-04", "2025-01-07")
        )

        self.assertFalse(_cobertura_incompleta(serie, "2025-01-01", "2025-01-10"))


if __name__ == "__main__":
    unittest.main()
