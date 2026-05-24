# Energy Ormuz Monitor

Dashboard de seguridad energética europea en el contexto del conflicto del Estrecho de Hormuz (inicio 28-feb-2026).

Documenta en tiempo real cómo evoluciona la situación energética europea — con foco especial en España — usando datos públicos y verificables: reservas de gas (GIE AGSI+), utilización de terminales LNG (GIE ALSI+) y flujos marítimos por el Estrecho (IMF PortWatch).

No es geopolítica especulativa. Es análisis de datos físicos que se actualizan solos.

## Estado

🔄 En construcción — Fase 1 (visualizador de estado actual).

## Stack

- Python 3.11+
- `gie-py` — cliente GIE AGSI+ / ALSI+
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
# Editar .streamlit/secrets.toml y añadir la API key de GIE
# (registro gratuito en https://agsi.gie.eu)

# 5. Lanzar el dashboard
streamlit run app.py
```

## Fuentes de datos

| Fuente | Dato | Acceso | Granularidad |
|---|---|---|---|
| GIE AGSI+ | Reservas gas subterráneo Europa/España | API REST, registro + key | Diaria desde 2011 |
| GIE ALSI+ | Terminales LNG Europa | Mismo API key que AGSI+ | Diaria desde 2012 |
| IMF PortWatch | Tráfico marítimo Hormuz | Público | Diaria |

## Estructura del repositorio

```
energy-ormuz-monitor/
├── app.py                      # dashboard principal Streamlit
├── data/
│   ├── __init__.py
│   ├── gie_client.py           # wrapper GIE API (AGSI+ y ALSI+)
│   └── portwatch_client.py     # wrapper IMF PortWatch
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

Por definir antes de hacer público el repositorio.
