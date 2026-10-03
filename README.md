# Energy Hormuz Monitor

Dashboard de seguridad energética europea en el contexto del conflicto del Estrecho de Ormuz (inicio 28-feb-2026).

Documenta en tiempo real cómo evoluciona la situación energética europea usando datos públicos y verificables: flujos marítimos por los principales chokepoints (IMF PortWatch), precio del crudo, reservas de crudo, existencias de productos y exportaciones de diésel de EEUU (EIA), reservas de gas subterráneo (GIE AGSI+), entrada de gas a la UE por gasoducto (ENTSOG), llegada de GNL a las terminales de regasificación (GIE ALSI), grados-día de calefacción (Open-Meteo) y reservas de emergencia (en días y por producto), origen del gas e importaciones de gasóleo por país (Eurostat).

No es geopolítica especulativa. Es análisis de datos físicos que se actualizan solos.

## Paneles

El dashboard sigue el recorrido del suministro: del estrecho al barril, y del barril al gas.

**Ormuz**

1. **Flujos marítimos** (IMF PortWatch): tránsito diario de buques. Ormuz por defecto, con selector para comparar con el Canal de Suez, Bab el-Mandeb, el Estrecho de Malaca, el Bósforo y el Canal de Panamá.

**Petróleo**

2. **Brent spot vs. reservas de crudo de EEUU** (EIA): precio diario del Brent frente a reservas estratégicas (SPR) y comerciales, con métricas de autonomía proyectada sobre suelos técnicos de referencia.
3. **Existencias comerciales de productos petrolíferos en EEUU** (EIA): destilado y jet fuel frente a suelos operativos estimados — la señal de urgencia de suministro a corto plazo — y días de cobertura calculados con la media de 4 semanas del *product supplied*.
4. **Diésel de EEUU hacia Europa** (EIA + Eurostat): exportaciones semanales de destilado, destinos mensuales y peso de EEUU en las importaciones europeas de gasóleo.
5. **Reservas de emergencia de petróleo UE-27** (Eurostat): días de autonomía por país.
6. **Reservas de emergencia por producto** (Eurostat): crudo, gasolina, jet, gasóleo y fuelóleo en miles de toneladas, con la variación mensual (qué producto sale del stock). Selector de país con UE-27 por defecto. Si algún país no reporta un mes, ese mes del agregado UE-27 queda en blanco y el caption lo lista.

**Gas**

7. **Reservas de gas subterráneo en Europa** (GIE AGSI+): nivel de llenado con comparativa interanual y selector de país, junto a los grados-día de calefacción del país seleccionado (Open-Meteo, reanálisis ERA5).
8. **Entrada de gas a la UE** (ENTSOG + GIE ALSI): cuánto gas entra cada día y por dónde — gasoductos por origen físico y GNL.
9. **Origen del gas importado** (Eurostat): mix de proveedores por país y agregado UE-27.
10. **Llegada de GNL a Europa** (GIE ALSI): llenado de los tanques de las terminales de regasificación frente al envío a la red y la capacidad máxima técnica. El diente de sierra del llenado es el pulso de descarga de metaneros: su aplanamiento es la alarma temprana de disrupción, visible el mismo día frente a los ~3 meses de desfase de Eurostat. Mide solo el canal GNL — el gas que entra por gasoducto no pasa por terminal y no aparece aquí.

La app incluye además un apartado **Metodología y limitaciones** con los desfases de publicación de cada fuente, el significado de los umbrales y lo que el monitor no mide.

## Stack

- Python 3.14
- `gie-py` — cliente GIE (AGSI+ y ALSI)
- `eurostat` — datos públicos Eurostat (sin key)
- `requests` — IMF PortWatch, EIA, ENTSOG y Open-Meteo
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
#      marcar acceso a AGSI y ALSI — una única key sirve para ambos
# PortWatch, Eurostat, ENTSOG y Open-Meteo son públicos y no necesitan key.

# 5. Lanzar el dashboard
streamlit run app.py
```

También puede abrirse en GitHub Codespaces: el dev container (`.devcontainer/`) instala las dependencias y arranca Streamlit en el puerto 8501.

## Tests

La suite usa `unittest` (biblioteca estándar) y cubre las funciones puras de transformación, los gráficos y los clientes de EIA, GIE y ENTSOG:

```bash
python -m unittest discover tests
```

## Fuentes de datos

| Fuente | Dato | Acceso | Granularidad |
|---|---|---|---|
| IMF PortWatch | Tráfico marítimo por chokepoint (Ormuz, Suez, Bab el-Mandeb, Malaca, Bósforo, Panamá) | Público | Diaria |
| EIA | Precio Brent spot | API REST + key | Diaria |
| EIA | Reservas de crudo EEUU: SPR (WCSSTUS1) y comerciales (WCESTUS1) | API REST + key | Semanal |
| EIA | Existencias de productos EEUU: destilado (WDISTUS1) y jet fuel (WKJSTUS1), y product supplied | API REST + key | Semanal |
| EIA | Exportaciones de destilado EEUU: total y por país de destino | API REST + key | Semanal / mensual |
| GIE AGSI+ | Reservas gas subterráneo Europa | API REST, registro + key | Diaria desde 2011 |
| GIE ALSI | Llegada de GNL: inventario de tanques y send-out de terminales | API REST, registro + key (la misma de AGSI+) | Diaria desde 2012 |
| ENTSOG | Entrada de gas por gasoducto: flujo físico y nominación por punto | Público, sin key | Diaria |
| Open-Meteo (ERA5) | Temperatura media diaria para grados-día de calefacción | Público, sin key | Diaria |
| Eurostat | Reservas de emergencia en días (nrg_stk_oem) | Público, sin key | Mensual |
| Eurostat | Reservas de emergencia por producto, en miles de toneladas (nrg_stk_oilm) | Público, sin key | Mensual |
| Eurostat | Origen del gas importado (nrg_ti_gasm) | Público, sin key | Mensual |
| Eurostat | Importaciones de gasóleo por origen (nrg_ti_oilm) | Público, sin key | Mensual |

## Estructura del repositorio

```
energy-ormuz-monitor/
├── app.py                      # dashboard principal Streamlit
├── data/
│   ├── __init__.py
│   ├── eia_client.py           # wrapper EIA API (Brent, crudo, productos y exportaciones)
│   ├── gie_client.py           # wrapper GIE API (AGSI+ y ALSI)
│   ├── entsog_client.py        # wrapper ENTSOG (gasoductos, público, sin key)
│   ├── portwatch_client.py     # wrapper IMF PortWatch
│   ├── eurostat_client.py      # wrapper Eurostat (público, sin key)
│   ├── open_meteo_client.py    # wrapper Open-Meteo ERA5 (público, sin key)
│   └── transform.py            # limpieza y transformación de todos los datasets
├── utils/
│   ├── __init__.py
│   └── charts.py               # funciones de visualización reutilizables
├── tests/                      # tests unitarios (unittest)
├── .streamlit/
│   ├── config.toml             # configuración Streamlit
│   └── secrets.toml.example    # plantilla (la real está en .gitignore)
├── .devcontainer/              # entorno para GitHub Codespaces
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

## Licencia

Este proyecto se distribuye bajo licencia [MIT](LICENSE).
