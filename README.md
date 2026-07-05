# Energy Ormuz Monitor

Dashboard de seguridad energética europea en el contexto del conflicto del Estrecho de Ormuz (inicio 28-feb-2026).

Documenta en tiempo real cómo evoluciona la situación energética europea usando datos públicos y verificables: flujos marítimos (IMF PortWatch), precio del crudo y reservas estratégicas y comerciales de EEUU (EIA), existencias de productos petrolíferos en EEUU (EIA), reservas de gas subterráneo (GIE AGSI+) y reservas de emergencia y origen del gas por país (Eurostat).

No es geopolítica especulativa. Es análisis de datos físicos que se actualizan solos.

## Estado

Fase 1 desplegada — 6 paneles en producción:

1. **Flujos marítimos — Estrecho de Ormuz** (IMF PortWatch): tráfico diario de buques con media móvil de 7 días.
2. **Brent spot vs. reservas de crudo de EEUU** (EIA): precio diario del Brent frente a reservas estratégicas (SPR) y comerciales, con métricas de autonomía proyectada sobre suelos técnicos de referencia.
3. **Reservas de gas subterráneo en Europa** (GIE AGSI+): nivel de llenado con comparativa interanual.
4. **Reservas de emergencia de petróleo UE-27** (Eurostat): días de autonomía por país.
5. **Origen del gas importado** (Eurostat): mix de proveedores por país y agregado UE-27.
6. **Existencias comerciales de productos petrolíferos en EEUU** (EIA): destilado y jet fuel frente a suelos operativos estimados — la señal de urgencia de suministro a corto plazo.

## Stack

- Python 3.14
- `gie-py` — cliente GIE AGSI+
- `eurostat` — datos públicos Eurostat (sin key)
- `requests` — IMF PortWatch
- `pandas` — series temporales
- `plotly` — visualización
- `streamlit` — dashboard
- Despliegue: Streamlit Community Cloud

## Instalación local

```bash
# 1. Clonar el repo
git clone https://github.com/LauraCGuzman/energy-ormuz-monitor.git
cd energy-ormuz-monitor

# 2. Crear y activar entorno virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Editar .streamlit/secrets.toml y añadir las API keys de EIA y GIE
# EIA: registro gratuito en https://www.eia.gov/opendata/
# GIE: registro gratuito en https://agsi.gie.eu

# 5. Lanzar el dashboard
streamlit run app.py
```

## Fuentes de datos

| Fuente | Dato | Acceso | Granularidad |
|---|---|---|---|
| IMF PortWatch | Tráfico marítimo Estrecho de Ormuz | Público | Diaria |
| EIA | Precio Brent spot | API REST + key | Diaria |
| EIA | Reservas de crudo EEUU: SPR (WCSSTUS1) y comerciales (WCESTUS1) | API REST + key | Semanal |
| EIA | Existencias de productos EEUU: destilado (WDISTUS1) y jet fuel (WKJSTUS1) | API REST + key | Semanal |
| GIE AGSI+ | Reservas gas subterráneo Europa | API REST, registro + key | Diaria desde 2011 |
| Eurostat | Reservas de emergencia en días (nrg_stk_oem) | Público, sin key | Mensual |
| Eurostat | Origen del gas importado (nrg_ti_gasm) | Público, sin key | Mensual |

## Estructura del repositorio

```
energy-ormuz-monitor/
├── app.py                      # dashboard principal Streamlit
├── data/
│   ├── __init__.py
│   ├── eia_client.py           # wrapper EIA API (Brent, crudo y productos)
│   ├── gie_client.py           # wrapper GIE API (AGSI+)
│   ├── portwatch_client.py     # wrapper IMF PortWatch
│   ├── eurostat_client.py      # wrapper Eurostat (público, sin key)
│   └── transform.py            # limpieza y transformación de todos los datasets
├── utils/
│   ├── __init__.py
│   └── charts.py               # funciones de visualización reutilizables
├── .streamlit/
│   ├── config.toml             # configuración Streamlit
│   └── secrets.toml.example    # plantilla (la real está en .gitignore)
├── requirements.txt
├── .gitignore
└── README.md
```

## Licencia

Este proyecto se distribuye bajo licencia [MIT](LICENSE).
