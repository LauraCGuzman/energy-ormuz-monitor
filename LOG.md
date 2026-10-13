# Log del proyecto

Incidencias de datos: síntoma → causa → arreglo → guarda. La más reciente, arriba.

## 2026-10-13 — Mismo pico en «Llegada de GNL a Europa»

- **Síntoma:** en la fila «envío a la red frente al máximo técnico» del panel de llegada de GNL, el 5/10/2026 marca 103.637 GWh/d y el eje se estira hasta ahí. Aplasta el resto de la serie (~3.500).
- **Causa:** el mismo dato de Ravenna (entrada siguiente). La guarda solo se aplicaba en el panel de entrada de gas, aunque los dos paneles leen el mismo `sendOut` de ALSI+.
- **Arreglo:** `transform_lng` (`data/transform.py`), un único punto común: `transform_gas` seguido de `sendout_gnl_validado`. Los dos paneles pasan por ahí y ya no llaman a la guarda cada uno por su cuenta.
- **Guarda:** la misma. En este panel el día descartado se ve como un corte de un día en la línea, y debajo aparece el mismo aviso (`texto_aviso_gnl_excluidos`). Tests: `tests/test_sendout_gnl.py::TestTransformLng`.

## 2026-10-13 — Pico espurio de GNL en «¿Cuánto gas entra hoy en la UE?»

- **Síntoma:** a partir del 5/10/2026, el GNL (media de 7 días) salta de ~3.500 a ~17.900 GWh/d y se queda plano una semana. Supera la capacidad de regasificación de toda la UE (~8.000 GWh/d).
- **Causa:** dato erróneo en la fuente. La terminal de Ravenna publicó en GIE ALSI+ un `sendOut` de 100.000,0 GWh/d el 5/10/2026 (status `C`, capacidad `dtrs` de 146,7; ~25 los días de alrededor). GIE lo suma al agregado de Italia (100.342) y al de la UE (103.636,8). El pipeline no tenía duplicados ni mezcla de niveles: no había ninguna comprobación de plausibilidad.
- **Arreglo:** `sendout_gnl_validado` (`data/transform.py`) deja ese día fuera de la media de 7 días. Sin caché en disco que regenerar: solo `st.cache_data` en memoria, con TTL de 1 h.
- **Guarda:** índice único y ascendente o `ValueError`; día con `sendOut` > `dtrs` o > 2 × mediana de los 30 días previos → excluido, registrado en el log y avisado en el panel. Sobre todo el histórico desde 2022 solo marca ese día. Tests: `tests/test_sendout_gnl.py`.
