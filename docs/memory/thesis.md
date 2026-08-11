# NSim — Informe de tesis

> Última actualización: 2026-08-11
> Responde a: "¿Cómo escribo el informe? ¿qué datos hay disponibles? ¿qué evalúa el corrector?"
> Actualizar cuando avance la escritura del informe.

---

## Contexto

Informe final de tesis de Daniel para titularse de Ingeniero Civil (Universidad de los Andes).
Modalidad: **Memoria** (investigación). Individual. ~30 páginas.

---

## Rúbrica Anexo 1 — lo que evalúa el corrector

| Indicador | Tipo | Peso | Lo que importa |
|---|---|---|---|
| Presentación y expresión escrita | A | 10% | Sin errores, formato consistente, figuras útiles |
| Resumen | A | 5% | Motivación + trabajo realizado + resultados/conclusiones |
| Introducción y motivación | B | 15% | Problema claro, motivación clara, alcance que coincide con lo hecho |
| Desarrollo | B | 20% | Tareas adecuadas para resolver el problema, bien detalladas |
| Análisis y conclusiones | B | 30% | Métodos adecuados, comparaciones, conclusiones justificadas |
| Referencias | A | 5% | Todas las aseveraciones relevantes referenciadas |
| Relevancia, alcance y novedad | B | 15% | Trabajo relevante para la especialidad, profundidad adecuada |

**Los indicadores tipo B suman el 80% de la nota.** Tipo A es presentación.

---

## Estrategia principal

Hacer la revisión fácil para el corrector: que pueda tener la pauta en la mano y señalar
exactamente en qué página se responde cada criterio.

- Definir objetivos de forma muy explícita en la introducción
- Cada sección del informe responde uno o más objetivos de forma identificable
- Los indicadores tipo B requieren que el lector evalúe pertinencia sin dificultad → claridad y estructura son clave

---

## Estado del material disponible (agosto 2026)

| Material | Estado |
|---|---|
| Código | ✅ Completo, 353 tests verdes |
| Docstrings | ✅ Todos revisados — listos para citar directamente en el informe |
| Telemetría SP1-SP6 | ✅ Completo |
| Pipeline de análisis | ✅ Funcional — genera gráficos y resúmenes de texto |
| SP7 (KPIs agregados) | 🔴 Pendiente — puede escribirse el informe sin esto |

---

## Datos y gráficos disponibles

Corrida más completa: `analysis/output/inicial_seed42_20260720-132250/`

| Archivo | Contenido |
|---|---|
| `passengers_station_funnel.png` | Flujo de pasajeros por estación |
| `passengers_time_histograms.png` | Distribución de tiempos de viaje |
| `modular_vehicles_fleet_overview.png` | Vista general de la flota |
| `modular_vehicles_trip_occupancy.png` | Ocupación por viaje |
| `slot_labels_*.png` (6 archivos) | Actividad de etiquetas de slot |
| `stations.txt` | KPIs por estación en texto |
| `passengers.txt` | Estadísticas de pasajeros |
| `modular_vehicles.txt` | Estadísticas de VMs |

Para regenerar: `python analysis.py` desde `NSim/` — ver `docs/memory/telemetry.md`.

---

## Qué puede citar el informe del código

El código está documentado para poder ser citado directamente:
- Cada módulo tiene docstring de arquitectura — útil para la sección de Desarrollo
- `CLAUDE.md` tiene el glosario, los invariantes y los contratos entre sistemas
- `config/constants.py` tiene todos los parámetros físicos con sus unidades
