# NSim — Telemetría y análisis

> Última actualización: 2026-08-11
> Responde a: "¿Qué SP está listo? ¿cómo corro el análisis? ¿qué gráficos genera?"
> Actualizar cuando se complete un SP o cambie la estructura de analysis/.
> Para SP7 pendiente y otros items → `docs/memory/backlog.md`

---

## Estado de sub-proyectos (SP)

| SP | Descripción | Estado |
|---|---|---|
| SP1 | Infraestructura base (recorder, JSONL, NullRecorder) | ✅ Completo |
| SP2 | Ciclo de vida del pasajero | ✅ Completo |
| SP2b | Correcciones de routing (disembark_all) | ✅ Completo |
| SP3 | Odómetro de VM (distancia, tiempo, eficiencia) | ✅ Completo |
| SP4 | Etiquetas de slot | ✅ Completo |
| SP5 | Árboles y junction routing (colisiones) | ✅ Completo |
| SP6 | Snapshots de estación | ✅ Completo |
| SP7 | Summary agregado (KPIs reales al final de corrida) | ✅ Completo |

Schema completo de eventos: `docs/events-schema.md`

---

## Cómo usar el pipeline de análisis

```bash
# Desde NSim/ — analiza la corrida más reciente en runs/
python analysis.py

# Analizar una corrida específica por run_id
python analysis.py inicial_seed42_20260720-132250
```

Los resultados se guardan en `analysis/output/<run_id>/` (carpeta en `.gitignore`).

---

## Módulos de analysis/ y qué generan

| Módulo | Gráficos generados | Texto generado |
|---|---|---|
| `passengers.py` | `passengers_time_histograms.png`, `passengers_station_funnel.png`, `passengers_transit.png` | Resumen: generados, abordaron, llegaron, tiempos; tabla por destino: dist, prom y mediana de viaje desde estación origen (`_travel_time_by_destination`) |
| `modular_vehicles.py` | `modular_vehicles_fleet_overview.png`, `modular_vehicles_km_efficiency.png`, `modular_vehicles_vm_reuse.png`, `modular_vehicles_trip_occupancy.png` | km totales, km útiles, eficiencia, tiempos |
| `stations.py` | — | Tabla: generados y llegados por estación |
| `slot_labels.py` | 6 gráficos `slot_labels_*.png` | — |
| `trees.py` | `trees_routing_balance.png`, `trees_reason_dist.png`, `trees_load_at_entry.png`, `trees_entry_margin.png`, `trees_collisions_timeline.png` (si hay datos) | — |

Módulos de soporte: `_shared.py` (IO/DB), `_style.py` (paleta y constantes visuales).

---

## Corrida de referencia para el informe

`analysis/output/inicial_seed42_20260720-132250/` — la más completa disponible.

Hallazgos verificados (escenario `inicial.py`, 3 estaciones):
- Flota: 1549 VMs totales; 1353 activos (87.5%)
- Viajes completados: 4730 | Ocupación boarding lane: 30.8%
- Distancia total: 129,265 km | Útil: 5,985 km | Eficiencia: 4.6%
- Imprecisión de distancia: 0.036% (aceptada para tesis — origen: desfase belt↔árbol)
- Estación 2: balance casi perfecto entre 4 andenes (25.5 / 25.2 / 24.8 / 24.5%)

---

## Estructura de archivos de telemetría en el proyecto

```
telemetry/
    recorder.py     — Recorder (buffer JSONL) y NullRecorder (sin overhead)

runs/               — Archivos JSONL de corridas (en .gitignore)
    <run_id>.jsonl

analysis/
    __main__.py     — Entry point
    _shared.py      — IO/DB: resolve_run, connect, get_output_dir, Reporter
    _style.py       — Visual: paleta, FIG_*, BAR_KWARGS, TITLE_SIZE
    passengers.py   — Análisis de pasajeros
    modular_vehicles.py — Análisis de flota
    stations.py     — Demanda y throughput por estación
    slot_labels.py  — Actividad de etiquetas de slot
    trees.py        — Routing y colisiones en árboles
    output/         — Resultados por run_id (en .gitignore)
```