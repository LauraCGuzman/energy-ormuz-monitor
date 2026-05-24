"""
Wrapper para el API público de IMF PortWatch.

IMF PortWatch publica datos diarios de tráfico marítimo por chokepoints
(Estrecho de Hormuz, Bab el-Mandeb, Suez, etc.) basándose en señales AIS.

Limitaciones documentadas:
    - GPS jamming en zona del Golfo desde feb-2026.
    - AIS spoofing detectado en buques que evitan ser identificados.
    - El dashboard debe incluir disclaimer explícito sobre estas limitaciones.
"""

from __future__ import annotations

import pandas as pd


PORTWATCH_BASE_URL = "https://portwatch.imf.org"


def fetch_chokepoint_flows(
    chokepoint: str = "hormuz",
    start: str = "2024-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Descarga el tráfico marítimo por un chokepoint.

    Args:
        chokepoint: identificador del estrecho ("hormuz", "bab_el_mandeb", "suez").
        start: fecha de inicio (YYYY-MM-DD).
        end: fecha de fin (None = hasta hoy).

    Returns:
        DataFrame con columnas: total_ships, tankers, lng_carriers, container_ships.
        Índice: fecha (datetime).
    """
    raise NotImplementedError
