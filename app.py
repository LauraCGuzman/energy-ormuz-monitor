"""
Monitor Energético Europa/Ormuz — Dashboard principal.

Visualiza el estado actual de la seguridad energética europea bajo el
contexto del conflicto del Estrecho de Hormuz (inicio 28-feb-2026):
    - Reservas de gas subterráneo (GIE AGSI+)
    - Utilización de terminales LNG (GIE ALSI+)
    - Flujos marítimos por el Estrecho (IMF PortWatch)

Punto de entrada: `streamlit run app.py`
"""

import streamlit as st

# Configuración de la página (debe ser la primera llamada a st)
st.set_page_config(
    page_title="Monitor Energético Ormuz",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    """Punto de entrada del dashboard."""
    st.title("Monitor Energético Europa/Ormuz")
    st.caption(
        "Datos físicos verificables sobre la situación energética europea "
        "desde el inicio del conflicto del Estrecho de Hormuz (28-feb-2026)."
    )

    st.info("🚧 En construcción — Fase 1.")

    # TODO: estructura prevista
    # 1. Sidebar con selector de país y rango de fechas
    # 2. KPIs superiores (nivel reservas España, % UE, flujo Hormuz vs baseline)
    # 3. Bloque AGSI+ — serie temporal reservas gas
    # 4. Bloque ALSI+ — utilización terminales LNG España
    # 5. Bloque PortWatch — flujos marítimos Hormuz
    # 6. Disclaimer sobre GPS jamming / AIS spoofing


if __name__ == "__main__":
    main()
