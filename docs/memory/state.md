# NSim — Estado de implementación

> Última actualización: 2026-08-11
> Responde a: "¿Qué está implementado? ¿cuántos tests? ¿qué falta?"
> Actualizar al cerrar una sesión en que algo cambie de estado.
> Para pendientes y backlog → `docs/memory/backlog.md`

---

## Resumen (agosto 2026)

- **353 tests, todos verdes**
- Código funcional al 100% — la simulación corre end-to-end con pygame
- Docstrings revisados en todos los módulos (253 correcciones, agosto 2026)
- Sin archivos vacíos pendientes

---

## Estado por módulo

### `objects/` — Completo con tests

| Archivo | Tests | Notas |
|---|---|---|
| `math3d.py` | ✅ | Vector3, operaciones geométricas 3D |
| `types.py` | ✅ | Enums de estado (ModularVehicleState, PassengerState, etc.) |
| `modular_vehicle.py` | ✅ | VM: identidad, capacidad, pasajeros, destino, posición |
| `passenger.py` | ✅ | Ciclo de vida y métricas de viaje |
| `passenger_id_generator.py` | ✅ | Contador global de IDs |
| `station.py` | ✅ | Genera pasajeros, acumula demanda, gestiona andenes |

### `tracks/` — Completo con tests

| Archivo | Tests | Notas |
|---|---|---|
| `base.py` | ✅ | BaseTrack ABC: geometría y contrato común |
| `boarding_lane.py` | ✅ | Velocidad constante + abordaje de pasajeros |
| `acceleration_tree.py` | ✅ | MRUA gravitacional; calcula su propia aceleración desde geometría |
| `junction.py` | ✅ | Punto de conexión belt↔árboles, routing, burst_capacity |

### `systems/` — Completo con tests

| Archivo | Tests | Notas |
|---|---|---|
| `continuous_train.py` | ✅ | Carril circular, slots, advance(), crossing detection |
| `network.py` | ✅ | Topología, update_all_tracks, process_transitions |
| `brain.py` | ✅ 74 tests | Ver desglose por clase más abajo |

### `simulation/` — Parcialmente con tests

| Archivo | Tests | Notas |
|---|---|---|
| `station_factory.py` | ✅ | Geometría 3D verificada; bug Y corregido (origin.y ≠ 0) |
| `simulation.py` | Sin test | Funcional y verificado corriendo |
| `camera.py` | Sin test | Cámara 3D perspectiva real, WASD + mouse look |
| `renderer.py` | Sin test | Wireframe 3D: VMs, árboles, estaciones, HUD, LOD |
| `inspector.py` | Sin test | Overlay de inspección interactiva al hacer click |
| `info_panel.py` | — | Eliminado — funcionalidad cubierta por `inspector.py` |

### `simulation_builder/` — Funcional, sin test automatizado

| Archivo | Estado | Notas |
|---|---|---|
| `inicial.py` | ✅ Corriendo | Escenario base: 3 estaciones (S2 con 3 andenes) |
| `linea_1.py` | ✅ Corriendo | Línea real de metro, 27 estaciones |
| `linea_1_edit.py` | ✅ Corriendo | Variante editable de linea_1 |
| `molde.py` | ✅ | Template para crear escenarios nuevos |

### `telemetry/` y `analysis/` — Completo

| Archivo | Estado |
|---|---|
| `telemetry/recorder.py` | ✅ JSONL con buffer; NullRecorder para modo sin telemetría |
| `analysis/` (7 módulos) | ✅ Pipeline completo — ver `docs/memory/telemetry.md` |

### `config/`

| Archivo | Estado |
|---|---|
| `config/constants.py` | ✅ Todas las constantes físicas y de simulación |

---

## Desglose de tests de brain.py (74 tests en 10 clases)

| Clase | Tests | Qué verifica |
|---|---|---|
| `TestBrainLoop` | 5 | Smoke test + orden de pasos del loop |
| `TestCounterAccounting` | 20 | Contabilidad de `on_vm_committed` / `on_commitment_broken` |
| `TestDestinationRedirect` | 8 | Redirección circular, monoestación sin alternativa |
| `TestCrossingHandler` | 6 | Ciclo de vida de etiquetas de slot en crossings |
| `TestLabelCompatibility` | 7 | Compatibilidad entre etiquetas reservation/destination/demand |
| `TestSaturationCheck` | 6 | `_would_saturate` unitario + integración |
| `TestDemandSystem` | 6 | Prioridades de `_range_search_demand` |
| `TestReservationMath` | 5 | Matemáticas: T_total, slot objetivo, aceleración MRUA, end-to-end |
| `TestRangeSearchPriorities` | 8 | 6 prioridades de `_range_search_reservation` |
| `TestBeltPlacement` | 3 | VM aterriza en slot reservado / fallback / `_reserved_slots` limpio |

---

## Cómo correr los tests

```bash
# Desde NSim/
pytest tests/ -q                    # todos (353)
pytest tests/test_brain.py -v       # solo brain (74)
pytest tests/ -q --tb=short         # con traceback corto en fallos
```

---

## Qué genuinamente no existe

- `simulation/info_panel.py` — eliminado (agosto 2026). Funcionalidad cubierta por `inspector.py`.
- `simulation/event_handler.py`, `vehicle_spawner.py`, `passenger_spawner.py` — nunca se crearon. Sus responsabilidades quedaron en `camera.py`/`renderer.py` y `station.update()`. No hacen falta.
- Los sistemas absorbidos en Brain que existían en Sim y fueron eliminados: `demand_manager.py`, `collision_predictor.py`, `consumption_manager.py`, `tree_selector.py`, `spatial_grid.py`.