# NSim — Schema de eventos de telemetría

> Última actualización: 2026-08-11
> Fuente de verdad: `telemetry/recorder.py` — si hay discrepancia, el código manda.
> Actualizar cuando se agreguen nuevos métodos al Recorder o cambie un SP de estado.
> Para estado de SPs y cómo correr análisis → `docs/memory/telemetry.md`

---

## Cómo leer los eventos

```python
# DuckDB — SIEMPRE con sample_size=-1
con.execute("SELECT * FROM read_ndjson_auto('runs/<run_id>/events.jsonl', sample_size=-1)")
```

`sample_size=-1` es obligatorio: sin él DuckDB infiere el schema de las primeras N líneas
y falla al encontrar campos que no aparecen en esa muestra (ej. `slot_reserved` aparece
mucho más tarde que `run_started`).

---

## Campos base (todos los eventos)

Cada línea JSONL tiene siempre estos 4 campos, más los específicos del tipo:

| Campo | Tipo | Descripción |
|---|---|---|
| `schema_version` | int | Versión del schema (actualmente 1) |
| `seq` | int | Contador monotónico — ordena eventos del mismo tick |
| `t` | float | Tiempo simulado en segundos |
| `type` | str | Nombre del evento (ej. `"run_started"`) |

---

## SP1 — Infraestructura base ✅

### `run_started`
Primera línea del archivo. `config` es generado por `simulation/run_config.py:extract_run_config`
— estructura fija, no varía por escenario.

| Campo | Tipo | Descripción |
|---|---|---|
| `config.run_id` | str | Identificador único (`<scenario>_seed<N>_<timestamp>`) |
| `config.seed` | int | Seed de aleatoriedad usada |
| `config.scenario_name` | str | Nombre del módulo de escenario (ej. `"inicial"`) |
| `config.belt` | dict | `total_length_m`, `max_slots`, `density`, `vm_capacity`, `junction_points` |
| `config.stations` | list[dict] | Por estación: `station_id`, `x/y/z`, `num_andenes`, `passenger_rate`, `vm_request_rate`, `destination_probabilities` |
| `config.constants` | dict | Todas las constantes físicas (GRAVITY, TRAIN_SPEED, TREE_DZ, BOARDING_COMMIT_PROGRESS, etc.) |

### `run_ended`
Emitido al cerrar la simulación. `summary` contiene métricas de ejecución, **no KPIs del servicio**
(esos corresponden a SP7, aún pendiente).

| Campo | Tipo | Descripción |
|---|---|---|
| `summary.simulated_seconds` | float | Tiempo simulado total (s) |
| `summary.train_laps` | float | Vueltas completas del tren (`t * TRAIN_SPEED / total_length`), 3 dec |
| `summary.build_seconds` | float | Tiempo de construcción del escenario (s) |
| `summary.sim_wall_seconds` | float | Tiempo real de simulación (s) |
| `summary.total_wall_seconds` | float | `build_seconds + sim_wall_seconds` |
| `summary.headless` | bool | `True` si corrió sin ventana pygame |
| `summary.ratio` | float | `simulated_seconds / sim_wall_seconds` — solo en headless |

### `run_manifest`
Última línea del archivo. Permite detectar qué event types están presentes en O(1)
sin recorrer todo el log. `t = -1`.

| Campo | Tipo | Descripción |
|---|---|---|
| `event_types` | list[str] | Todos los tipos de evento que aparecen en el archivo |

---

## SP2 — Ciclo de vida del pasajero ✅

### `passenger_spawned`

| Campo | Tipo | Descripción |
|---|---|---|
| `passenger_id` | int | ID único del pasajero |
| `origin_station_id` | int | Estación donde fue generado |
| `destination_station_id` | int | Estación de destino |

### `passenger_boarded`
Emitido al alcanzar `BOARDING_COMMIT_PROGRESS` — el embarque es definitivo desde aquí.

| Campo | Tipo | Descripción |
|---|---|---|
| `passenger_id` | int | |
| `vm_id` | int | VM que lo recogió |
| `spawn_time` | float | Copia de `passenger_spawned.t` — `wait_time = t - spawn_time`, sin JOIN |

### `passenger_transit`
VM del pasajero entró a una estación intermedia; el pasajero no bajó (no era su destino).

| Campo | Tipo | Descripción |
|---|---|---|
| `passenger_id` | int | |
| `vm_id` | int | |
| `station_id` | int | Estación que el VM visitó de paso |

### `passenger_arrived`
Pasajero llegó a su estación destino correcta.

| Campo | Tipo | Descripción |
|---|---|---|
| `passenger_id` | int | |
| `station_id` | int | Estación de desembarco (correcta) |
| `spawn_time` | float | `travel_time = t - spawn_time`, sin JOIN |

### `passenger_arrived_wrong`
Pasajero bajó en una estación que NO era su destino (VM fue redirigido).

| Campo | Tipo | Descripción |
|---|---|---|
| `passenger_id` | int | |
| `station_id` | int | Estación donde bajó (incorrecta) |
| `expected_station_id` | int | Estación donde debía haber bajado |
| `spawn_time` | float | Para calcular tiempo total incluyendo errores de routing |

---

## SP2b — Correcciones de routing ✅

### `vm_redirected`
VM no pudo entrar a su estación destino (árboles saturados) y fue redirigido a la siguiente.

| Campo | Tipo | Descripción |
|---|---|---|
| `vm_id` | int | |
| `blocked_station_id` | int | Estación a la que no pudo entrar |
| `redirected_to_station_id` | int | Estación alternativa elegida |
| `passenger_count` | int | Pasajeros a bordo al momento de la redirección |

### `vm_placed_without_reservation`
VM bajó al carril sin reserva previa. Indica un bug en el scheduler de reservas — no debería
ocurrir en corridas normales.

| Campo | Tipo | Descripción |
|---|---|---|
| `vm_id` | int | |
| `station_id` | int | Estación desde la que bajó |
| `fallback_slot_idx` | int | Slot donde se colocó como fallback |

---

## SP3 — Odómetro de VM ✅

### `vm_created`
Emitido una vez por VM al iniciar la simulación.

| Campo | Tipo | Descripción |
|---|---|---|
| `vm_id` | int | ID único del VM |

### `vm_trip_completed`
VM completó el recorrido de un boarding lane (con o sin pasajeros).

| Campo | Tipo | Descripción |
|---|---|---|
| `vm_id` | int | |
| `passenger_count` | int | Pasajeros transportados. `0` = pasada vacía |
| `lane_length` | float | Longitud del boarding lane recorrido (m) |

Un viaje "útil" se define como `passenger_count > 0`.

### `vm_run_summary`
Emitido una vez por VM al cerrar la simulación.

| Campo | Tipo | Descripción |
|---|---|---|
| `vm_id` | int | |
| `total_distance` | float | Distancia total recorrida (m) — todos los segmentos |
| `operational_time` | float | Tiempo total activo (s) |
| `distance_carrying_passengers` | float | Distancia recorrida con ≥ 1 pasajero a bordo (m) |

> **Nota de precisión:** `distance_carrying_passengers` tiene un error ≤ 0.036% por
> desfases de ≤ 0.67m en cada cruce belt↔árbol (overcounting al salir, undercounting
> al llegar). Medido en run `inicial_seed42_20260720-132250` sobre 129,265 km totales.
> Aceptado para tesis.

---

## SP4 — Etiquetas de slot ✅

Diez eventos que trazan el ciclo de vida del sistema de reserva y anti-colisión de Brain.
Se emiten desde `brain.py` al llamar métodos de etiquetado de `ContinuousTrain`.

### `slot_reserved`
Brain reserva un slot para que un VM descendente aterrice en él.

| Campo | Tipo | Descripción |
|---|---|---|
| `slot_idx` | int | Slot reservado |
| `station_id` | int | Estación de la boarding lane (origen del VM) |
| `vm_id` | int | VM que descenderá a este slot |
| `target_idx` | int | Slot ideal calculado por `_make_reservation` antes de ajuste |
| `slot_offset` | int | Desplazamiento real respecto al ideal (`best_slot - target_idx`) |
| `priority` | str | Prioridad del slot elegido (ver búsqueda en rango en CLAUDE.md) |
| `T_total` | float | Tiempo total calculado (lane + DOWN tree) en segundos, 4 dec |
| `accel` | float | Aceleración ajustada del árbol DOWN (m/s²), 4 dec |
| `prev_labels` | dict | Estado del slot ANTES de ser reservado |

### `slot_reservation_cleared`
Reserva liberada.

| Campo | Tipo | Descripción |
|---|---|---|
| `slot_idx` | int | |
| `station_id` | int | |
| `reason` | str | `'vm_arrived'` — VM aterrizó en el slot; `'missed_junction'` — slot pasó la junction sin VM |

### `slot_demand_set`
Brain marca un slot para satisfacer demanda pendiente de una estación.

| Campo | Tipo | Descripción |
|---|---|---|
| `slot_idx` | int | |
| `station_id` | int | Estación con demanda pendiente |
| `priority` | str | Prioridad del slot elegido |
| `prev_labels` | dict | Estado del slot ANTES de marcarlo |

### `slot_demand_cleared`
Etiqueta de demanda limpiada.

| Campo | Tipo | Descripción |
|---|---|---|
| `slot_idx` | int | |
| `station_id` | int | |
| `reason` | str | `'vm_entered_tree'` — promesa cumplida; `'commitment_broken'` — árbol rechazó el VM |

### `slot_destination_set`
Brain escribe el destino del VM en el slot (anticipado antes de que el VM llegue al carril).

| Campo | Tipo | Descripción |
|---|---|---|
| `slot_idx` | int | |
| `station_id` | int | Estación destino del VM |
| `vm_id` | int \| None | VM al que corresponde (None si aún no aterrizó) |
| `source` | str | `'boarding_commit'`, `'reservations_pass'`, o `'redirect'` |
| `prev_dest` | int \| None | Destino anterior del slot (para detectar sobreescrituras) |

### `slot_destination_cleared`
Destino limpiado cuando el VM sale del slot hacia el árbol UP.

| Campo | Tipo | Descripción |
|---|---|---|
| `slot_idx` | int | |
| `station_id` | int | |

### `junction_vm_entered`
VM entró al árbol UP de la estación desde el carril.

| Campo | Tipo | Descripción |
|---|---|---|
| `station_id` | int | |
| `vm_id` | int | |
| `slot_idx` | int | Slot que ocupaba el VM en el carril |
| `forced` | bool | `True` si se usó `force_add_vm` (entrada garantizada por reserva) |

### `junction_commitment_broken`
Árbol rechazó VM de demanda — compromiso roto, VM sigue en belt.

| Campo | Tipo | Descripción |
|---|---|---|
| `station_id` | int | |
| `vm_id` | int | |
| `slot_idx` | int | |

### `slot_collision`
Dos VMs terminaron en el mismo slot — la reserva falló o llegó tarde.

| Campo | Tipo | Descripción |
|---|---|---|
| `slot_idx` | int | |
| `vm_arriving_id` | int | VM que intentó aterrizar |
| `vm_occupying_id` | int | VM que ya estaba en el slot |
| `prev_labels` | dict | Estado del slot justo antes de la colisión |

### `slot_search_completed`
Resultado de una búsqueda de slot candidato (para reserva o demanda).

| Campo | Tipo | Descripción |
|---|---|---|
| `context` | str | Contexto de la búsqueda (ej. `'reservation'`, `'demand'`) |
| `station_id` | int | Estación que origina la búsqueda |
| `selected_slot_idx` | int \| None | Slot elegido (`None` si no se encontró candidato) |
| `selected_priority` | str | Prioridad del slot elegido |
| `window` | list | Candidatos evaluados (para debug de saturación) |

---

## SP5 — Árboles y colisiones en track ✅

### `tree_vm_entered`
VM entró a un árbol UP. `tree_idx` es el índice del andén dentro del junction.

| Campo | Tipo | Descripción |
|---|---|---|
| `station_id` | int | |
| `tree_idx` | int | Índice del andén elegido dentro del junction (0-based) |
| `vm_id` | int | |
| `forced` | bool | `True` si fue `force_add_vm` |
| `reason` | str | Razón de la entrada (`'reserved'`, `'destination'`, `'demand'`, `'unplanned'`) |
| `vehicle_count_after` | int | VMs en el árbol después de la entrada |
| `nearest_existing_distance` | float \| None | Distancia al VM más cercano en el árbol (None si el árbol estaba vacío) |

### `track_collision_started`
Dos VMs en el mismo track se acercaron a menos de `TRAIN_VM_LENGTH`.

| Campo | Tipo | Descripción |
|---|---|---|
| `track_id` | int | |
| `vm_id_1` | int | |
| `vm_id_2` | int | |
| `separation` | float | Distancia entre los dos VMs al detectarse la colisión (m) |
| `pos_x` | float | Posición X del punto medio entre los VMs |
| `pos_y` | float | |
| `pos_z` | float | |

### `track_collision_ended`
Par colisionando volvió a separación ≥ `TRAIN_VM_LENGTH` o uno salió del track.

| Campo | Tipo | Descripción |
|---|---|---|
| `track_id` | int | |
| `vm_id_1` | int | |
| `vm_id_2` | int | |
| `separation` | float | Separación al resolverse la colisión (m) |
| `pos_x` | float | |
| `pos_y` | float | |
| `pos_z` | float | |
| `reason` | str | `'separated'` o `'vm_exited'` |

---

## SP6 — Snapshots de estación ✅

### `station_snapshot`
Emitido periódicamente desde `Brain.update()`. Habilita series de tiempo de ocupación.

| Campo | Tipo | Descripción |
|---|---|---|
| `station_id` | int | |
| `active_anden_count` | int | Andenes activos en este momento |
| `pending_demand` | int | Demanda pendiente (puede ser negativa — `on_unplanned_vm_at_tree`) |
| `andenes` | list[dict] | Un dict por andén (ver subcampos abajo) |

Cada elemento de `andenes` contiene:

| Subcampo | Tipo | Descripción |
|---|---|---|
| `anden_idx` | int | Índice del andén dentro de la estación |
| `active` | bool | Si el andén está en estado ACTIVE |
| `queue_total` | int | Total de pasajeros esperando en todos los grupos |
| `queues` | list[dict] | Por destino: `{destination_station_id, waiting_count}` (solo grupos no vacíos) |
| `vm_count` | int | VMs actualmente en la boarding lane |
| `vms_boarding` | int | VMs con pasajeros pero sin commit aún |
| `vms_committed_pax` | int | VMs con pasajeros y commit realizado |
| `vms_empty_pre` | int | VMs vacíos sin commit |
| `vms_empty_post` | int | VMs vacíos con commit (pasada en vacío) |

---

## SP7 — Summary agregado ✅

Los KPIs reales del sistema están disponibles a través del pipeline de `analysis.py`,
que los calcula desde los eventos de SP1-SP6 y genera los gráficos del informe.

`run_ended.summary` contiene las métricas de ejecución (ver SP1 arriba). Los KPIs
de servicio (tiempos de viaje, ocupación, throughput por estación) los produce
`analysis.py` — ver `docs/memory/telemetry.md` para cómo correrlo.
