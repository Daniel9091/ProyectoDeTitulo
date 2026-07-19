# NSim — Schema de eventos de telemetría

Los eventos se escriben desde `simulation/recorder.py` a un archivo JSONL en
`runs/<run_id>.jsonl`. Cada línea es un objeto JSON con al menos `type` y `t`
(tiempo de simulación en segundos).

**Leer con DuckDB:**
```python
con.execute("SELECT * FROM read_ndjson_auto('runs/archivo.jsonl', sample_size=-1)")
```

El `sample_size=-1` es obligatorio: sin él DuckDB infiere el schema de las primeras N
líneas y falla al encontrar campos que no aparecen en esa muestra.

---

## SP1 — Infraestructura base ✅

### `run_started`
Primera línea del archivo. Metadatos de la corrida.

| Campo | Tipo | Descripción |
|---|---|---|
| `t` | float | 0.0 |
| `run_id` | str | Identificador único de la corrida (timestamp) |
| `n_stations` | int | Número de estaciones en la red |
| `train_speed` | float | Velocidad del carril circular (m/s) |

### `run_ended`
Emitido al cerrar la simulación.

| Campo | Tipo | Descripción |
|---|---|---|
| `t` | float | Tiempo final de simulación (s) |

### `run_manifest`
Última línea del archivo. Permite detectar qué event types están presentes en O(1),
sin recorrer todo el log.

| Campo | Tipo | Descripción |
|---|---|---|
| `t` | float | Igual a `run_ended.t` |
| `event_types` | list[str] | Todos los tipos de evento que aparecen en el archivo |

---

## SP2 — Ciclo de vida del pasajero ✅

### `passenger_spawned`
Emitido cuando una estación genera un pasajero.

| Campo | Tipo | Descripción |
|---|---|---|
| `t` | float | Tiempo de generación (s) |
| `passenger_id` | int | ID único del pasajero |
| `origin_station_id` | int | Estación donde fue generado |
| `destination_station_id` | int | Estación de destino |

### `passenger_boarded`
Emitido cuando un VM recoge a un pasajero en el boarding lane.

| Campo | Tipo | Descripción |
|---|---|---|
| `t` | float | Tiempo de abordaje (s) |
| `passenger_id` | int | |
| `vm_id` | int | VM que lo recogió |
| `spawn_time` | float | Copia de `passenger_spawned.t` — permite calcular `wait_time = t - spawn_time` sin JOIN |

### `passenger_arrived`
Emitido cuando el pasajero llega a su destino correcto.

| Campo | Tipo | Descripción |
|---|---|---|
| `t` | float | Tiempo de llegada (s) |
| `passenger_id` | int | |
| `station_id` | int | Estación de desembarco (correcta) |
| `spawn_time` | float | Permite calcular `travel_time = t - spawn_time` sin JOIN |

### `passenger_arrived_wrong`
Emitido cuando el pasajero es desembarcado en una estación incorrecta.

| Campo | Tipo | Descripción |
|---|---|---|
| `t` | float | Tiempo de desembarco (s) |
| `passenger_id` | int | |
| `station_id` | int | Estación donde fue desembarcado (incorrecta) |

> **Deuda técnica (baja prioridad):** `passenger_arrived` y `passenger_arrived_wrong`
> no incluyen `vm_id`.

---

## SP3 — Odómetro de VM ✅

### `vm_created`
Emitido una vez por VM al iniciar la simulación, desde `Brain._register_initial_vms()`.

| Campo | Tipo | Descripción |
|---|---|---|
| `t` | float | 0.0 |
| `vm_id` | int | ID único del VM |

### `vm_trip_completed`
Emitido cuando un VM termina de recorrer un boarding lane (con o sin pasajeros).

| Campo | Tipo | Descripción |
|---|---|---|
| `t` | float | Tiempo de salida del boarding lane (s) |
| `vm_id` | int | |
| `passenger_count` | int | Pasajeros transportados. `0` = pasada vacía |
| `lane_length` | float | Longitud del boarding lane recorrido (m) |

Un "viaje válido" se define como `passenger_count > 0`.

### `vm_run_summary`
Emitido una vez por VM al cerrar la simulación.

| Campo | Tipo | Descripción |
|---|---|---|
| `t` | float | Tiempo final de simulación (s) |
| `vm_id` | int | |
| `total_distance` | float | Distancia total recorrida (m) — todos los segmentos |
| `operational_time` | float | Tiempo total activo (s) |
| `distance_carrying_passengers` | float | Distancia recorrida con ≥ 1 pasajero a bordo (m) |

> **Nota de precisión:** `distance_carrying_passengers` tiene un error ≤ 0.036% por
> desfases de ≤ 0.67m en cada cruce belt↔árbol (overcounting al salir, undercounting
> al llegar — signos opuestos, compensación parcial).
> Medido en run `20260718-144520` sobre 129,265 km totales. Aceptado para tesis.

---

## SP4 — Etiquetas de slot 🔴 *(pendiente)*

Seis eventos que tracean el ciclo de vida del sistema de reserva y anti-colisión de
`Brain`. Se emiten desde `brain.py` al llamar a los métodos de etiquetado de
`ContinuousTrain`.

| Evento | Cuándo se emite |
|---|---|
| `slot_reserved` | Brain reserva un slot para que un VM descendente aterrice |
| `slot_reservation_cleared` | El VM aterrizó (`place_vm`) o el slot pasó el junction sin VM |
| `slot_demand_set` | Brain marca un slot para satisfacer demanda de una estación |
| `slot_demand_cleared` | El VM entró al árbol de subida o el slot pasó el junction |
| `slot_destination_set` | Brain escribe el destino del VM en el slot (al hacer commit en boarding lane) |
| `slot_destination_cleared` | El VM sale del carril hacia el árbol de subida (`remove_vm`) |

Campos exactos por definir al implementar SP4.

---

## SP5 — Eventos de seguridad 🔴 *(pendiente)*

| Evento | Origen | Descripción |
|---|---|---|
| `vm_near_collision` | `AccelerationTree.force_add_vehicle()` | Reemplaza el `print` de advertencia actual |
| `vm_slot_conflict` | `ContinuousTrain.place_vm()` | Defensivo: slot ocupado al intentar aterrizar |

---

## SP6 — Snapshots de estación 🔴 *(pendiente)*

### `station_snapshot`
Emitido periódicamente (cada N segundos) desde `Brain.update()`.
Requiere agregar `passengers_waiting` y `vms_in_lane` a `Station`.

Habilita: series de tiempo de ocupación de estaciones y VMs en tránsito.

---

## SP7 — Vueltas del tren 🔴 *(pendiente)*

Métrica derivada al cierre: `MAX(t) * TRAIN_SPEED / train_total_length`.
Requiere incluir `train_total_length` en el evento `run_started`.
