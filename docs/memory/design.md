# NSim — Decisiones de diseño técnico

> Última actualización: 2026-08-11
> Decisiones no obvias de implementación que NO son deducibles solo leyendo los docstrings.
> Leer cuando vayas a modificar AccelerationTree, Junction, ContinuousTrain o Brain.
> Para el loop de 8 pasos → CLAUDE.md §Brain. Para invariantes generales → CLAUDE.md §Invariantes.

---

## ContinuousTrain — slots y etiquetas

### Los 5 campos del slot dict

Cada slot es un dict con 5 campos **independientes** — todos pueden estar activos simultáneamente:

```python
{
    'vm':                     ModularVehicle | None,  # presencia física
    'reserved_station_id':    int | None,             # anticolicisón — guarda station_id, NO vm_id
    'reserved_vm_id':         int | None,             # qué VM viene (Brain mantiene _reserved_slots: dict[vm_id→slot_idx] aparte)
    'destination_station_id': int | None,             # routing — dónde debe salir el VM
    'demand_station_id':      int | None,             # taza — slot comprometido para suplir demanda
}
```

Qué limpia cada operación:
- `place_vm` → limpia `reserved_station_id` y `reserved_vm_id`; escribe `vm`
- `remove_vm` → limpia `destination_station_id` y `demand_station_id`; limpia `vm`
- `clear_demand_supply` → limpia solo `demand_station_id`

### Por qué `self.vehicles` guarda `distance` (metros), no `progress` (normalizado)

`progress = distance / length` se calcula on-demand con `get_progress()`. Si se guardara progress y se actualizara cada frame con `+= delta / length`, se acumularía error de punto flotante por divisiones repetidas. La distancia es exacta; dividir una vez al leer es más limpio.

---

## AccelerationTree — decisiones de implementación

### Una sola clase con parámetro `direction: TreeDirection`

No hay dos clases `UPTree` y `DOWNTree`. La diferencia está en los parámetros:

| | UP tree | DOWN tree |
|---|---|---|
| Velocidad de entrada | `TRAIN_SPEED` | `BOARDING_LANE_SPEED` |
| Aceleración con signo | `−base_acceleration` (frena) | `+base_acceleration` (acelera) |
| ¿Puede saturar? | Sí — `can_accept()` puede dar False | No — siempre acepta |

### `base_acceleration` se calcula internamente desde geometría

No es parámetro del constructor. Se calcula en `_compute_effective_acceleration()` desde `dz = |end_pos.z - start_pos.z|` y `GRAVITY`. Si `dz ≤ 0` lanza `ValueError` — fail-fast, no degrada a aceleración cero. `station_factory.py` calcula la geometría; el árbol calcula su propia física.

### `target_acceleration` es por VM, no por árbol

Guardado en `self.vehicles[vm_id]['target_acceleration']`. Múltiples VMs en el mismo DOWN tree pueden tener aceleraciones distintas — Brain ajusta la de cada VM para que aterrice en su slot reservado.

### Patrón `reserved_tree_acceleration` (anticolicisón en DOWN trees)

El sistema de reserva calcula la aceleración del DOWN tree UNA SOLA VEZ al seleccionar el slot:
1. `_make_reservation()` calcula la aceleración ajustada `a` para que el VM llegue al slot correcto
2. La guarda en `vm.reserved_tree_acceleration: float | None`
3. Al entrar al DOWN tree, `_insert_vehicle()` lee ese valor:
   - Si no es None → lo usa como `target_acceleration` y lo pone a None (consumido)
   - Si es None → usa `base_acceleration` (pase sin reserva, funciona correctamente)

Esto evita recalcular la aceleración al momento de insertar — el cálculo ya se hizo con la información correcta del slot.

### `ACCEL_RANGE` es un soft constraint, no un clamp

`ACCEL_RANGE_MIN` y `ACCEL_RANGE_MAX` son rangos de comodidad del pasajero. `set_vehicle_acceleration()` imprime `[ADVERTENCIA]` si se sale del rango, pero guarda el valor sin modificar. Brain puede y debe aplicar cualquier aceleración necesaria en emergencias anticolicisón aunque esté fuera del rango cómodo. **No clampea.** El bug original clampeaba — fue corregido en julio 2026.

---

## Junction — implementación

### Dos Junctions por estación, propósito distinto

| | Junction UP | Junction DOWN |
|---|---|---|
| Qué pasa | VMs salen del belt hacia arriba | VMs llegan al belt desde arriba |
| Saturación | Posible — `can_accept()` puede dar False | Nunca — DOWN trees siempre aceptan |
| `burst_window` | `trees[0].min_slot_gap` (> 0) | 0 (sin saturación) |

Junction va en `tracks/junction.py` — NO en `objects/` porque necesita importar `AccelerationTree`. En `objects/` causaría import circular. No hereda de `BaseTrack` (no gestiona vehículos propios, no tiene `update()`).

### `add_vm` — distribución por carga mínima

```python
def add_vm(self, vehicle, leftover_dt=0.0) -> tuple[bool, int | None]:
    for tree in sorted(self.trees, key=lambda t: t.vehicle_count):
        if tree.add_vehicle(vehicle, leftover_dt=leftover_dt):
            return True, self.trees.index(tree)
    return False, None
```

Itera árboles ordenados por `vehicle_count` (el menos cargado primero). El mismo código funciona para Junction DOWN porque los DOWN trees siempre retornan True.

### `force_add_vm` — árbol más seguro para entrada forzada

```python
def _least_saturated_tree(self) -> AccelerationTree:
    def youngest_distance(tree):
        if not tree.vehicles:
            return float('inf')
        return min(data['distance'] for data in tree.vehicles.values())
    return max(self.trees, key=youngest_distance)
```

Para forzar entrada, el criterio cambia: no el menos cargado, sino el que tiene al VM más joven (más lejano de la entrada, o sea más adentro del árbol). `youngest_distance` = mínima distancia entre todos los VMs = el VM más cercano a la entrada. Se elige el árbol donde ese VM está más adentro → mayor margen para el nuevo.

### `min_slot_gap` usa `math.ceil` deliberadamente

`dt_min * TRAIN_SPEED / TRAIN_SPACING` puede dar 2.3 slots. Redondear hacia abajo (floor) daría gap insuficiente → posible colisión. `ceil` da holgura segura aunque desperdicie medio slot.

### Comportamiento bursty de la capacidad

Con N=3 árboles y G=9 slots de burst_window:
```
slots:  0  1  2  3  4  5  6  7  8  9  10  11  12 ...
puede:  ✓  ✓  ✓  ✗  ✗  ✗  ✗  ✗  ✗  ✓   ✓   ✓   ✗ ...
```
3 VMs consecutivos entran, luego 6 slots de espera, luego 3 más. **BURSTY, no "1 VM cada 3 slots".** Esto es importante para el sistema de reserva: al buscar candidatos, hay ráfagas naturales de capacidad, no distribución uniforme.

---

## BaseTrack — contrato de la interfaz

### `update(dt, current_time=0.0) -> list[tuple[vm, leftover_dt]]`

Contrato que toda subclase debe respetar. `current_time` es opcional (default 0.0) — se usa para timestamps de telemetría. Los tests que no pasan `current_time` siguen siendo compatibles. El caller usa `leftover_dt` para `next_track.add_vehicle(vm, leftover_dt=...)`.

### Patrón `_compute_advance` — un método privado por subclase

Cada subclase implementa su propia fórmula de movimiento:

| Subclase | Física | Firma | Fórmula |
|---|---|---|---|
| `BoardingLane` | MRU (velocidad constante) | `(velocity, dt)` | `v * dt` |
| `AccelerationTree` | MRUA (aceleración gravitacional) | `(velocity, dt, acceleration)` | `v0*t + 0.5*a*t²` |

La `acceleration` ya lleva signo: negativa para UP trees (frena), positiva para DOWN trees (acelera). No se pasa el valor absoluto.

---

## Network — estructura y diseño

### Estructura de la clase

```python
class Network:
    tracks: dict[int, BaseTrack]           # track_id → objeto (todos los tracks)
    adjacency: dict[int, list[int]]        # track_id → [next_track_ids] (uno-a-muchos)
    junctions_up: dict[int, Junction]      # station_id → Junction UP
    junctions_down: dict[int, Junction]    # station_id → Junction DOWN
    stations: dict[int, Station]           # station_id → Station (para notificaciones)
    continuous_train: ContinuousTrain      # (o dict si hay múltiples trenes en el futuro)
```

### Regla de transición en `process_transitions()`

| `len(adjacency[track_id])` | Qué pasa | Quién decide |
|---|---|---|
| `== 1` | Transición mecánica — solo hay un destino posible | `Network` ejecuta directamente |
| `> 1` | Decisión de routing — hay más de un next track | `Brain` elige cuál |
| `== 0` | DOWN tree terminal — VM llega al belt | Va a `pending_belt_placements` para `Brain` |

### Por qué Option B (grafo 1→N) y no Option A (dataclass Andén)

Option A asume el invariante: exactamente 1 UP tree + 1 boarding lane + 1 DOWN tree por andén. Esa invariante se rompe con la arquitectura futura:

- **Dos trenes paralelos**: 1 boarding lane ← 2 UP trees (de trenes distintos)
- **Cambio de línea**: 1 boarding lane → 2 DOWN trees (uno por dirección)
- **Lanes de acumulación**: topología variable según demanda

Sim usó un grafo de adyacencia (Option B) pero mezcló decisiones de routing dentro de Network. NSim separa: `Network` = topología + mecánica; `Brain` = decisiones. Si se toca esta separación aparece acoplamiento oculto y la arquitectura futura se bloquea.

---

## Station — interfaz con Brain

### `pending_demand` puede ser negativo

Brain interpreta `station.pending_demand` así:

| Valor | Significado | Acción de Brain |
|---|---|---|
| `> 0` | La estación necesita VMs | Buscar y marcar slots |
| `= 0` | Equilibrio | No hacer nada |
| `< 0` | Exceso de VMs comprometidos | No solicitar más |

El acumulador puede ir negativo y se autorregula. No es un error — significa que llegaron VMs no planeados que cubrieron demanda antes de que Brain los solicitara.

### Los tres callbacks de Brain sobre Station

```python
station.on_vm_committed()          # Brain marcó un slot para esta estación → acumulador -= 1
station.on_commitment_broken()     # VM marcado fue rechazado por todos los árboles → acumulador += 1
station.on_unplanned_vm_at_tree()  # VM no marcado entró al árbol UP → acumulador -= 1 (puede ir negativo)
```

El tercer callback existe porque un VM puede subir a una estación sin haber sido solicitado (pasó por ahí, tenía destino ahí por otra vía). Brain lo descuenta igual para que el acumulador refleje la realidad.

---

## Problema Destino Terminal — diseño

Muchos VMs con el mismo destino X pueden llegar simultáneamente y saturar la Junction UP de X.

**Solución diseñada:** al asignar `destination_station_id` en `_make_reservation`, verificar que el slot candidato W no incremente la densidad de VMs con destino X por encima de `burst_capacity` en ninguna ventana de `burst_window` slots.

**El check es local a W — O(burst_window):**
- Revisar solo `[W-(burst_window-1), W+(burst_window-1)]`
- Para cada sub-ventana de tamaño `burst_window` que contenga a W, contar slots con `destination == X` (excluyendo W)
- Si alguna sub-ventana ya tiene ≥ `burst_capacity` → rechazar destino X para ese slot

No hay que mirar más allá del rango local — por invariante inductivo, lo que está fuera del rango ya fue validado cuando se asignó.

**⚠️ Decisión de arquitectura pendiente antes de implementar:**
¿slot-first (elegir slot y luego verificar destinos bloqueados) o destination-first (bloquear destinos y luego buscar slot libre)?
Esta decisión afecta el orden completo de `_make_reservation`. **SIN ESTA DECISIÓN, NO IMPLEMENTAR.**

---

## Principios de acoplamiento entre capas

Reglas que el sistema entero respeta:

- `objects/` no importa nada del proyecto
- `Station` solo conoce `tree_ids` (int) — `Network` resuelve IDs a objetos
- `Brain` es el único coordinador entre capas — nadie más toma decisiones de routing
- `ContinuousTrain` no toma decisiones — solo expone datos y estados
- `AccelerationTree` no conoce `ContinuousTrain` ni `Station`

Si alguna de estas reglas se rompe, aparecen imports circulares o acoplamiento oculto.

### PassengerIdGenerator — una instancia por simulación

Dependency-injected a cada `Station`. Garantiza IDs únicos entre estaciones sin límite por estación. No usar un contador por estación (colisión de IDs si dos estaciones generan el mismo número).

---

## Invariante de topología — tracks saturables solo via Junction

Un `AccelerationTree` UP (el único tipo que puede saturar) solo debe ser alcanzable a través de una `Junction`, nunca por transición mecánica directa (`len==1` en `network.process_transitions`).

**Por qué:** las transiciones mecánicas no tienen routing — el VM solo puede ir a un lugar. Si ese lugar está saturado, no hay alternativa. La Junction es quien conoce todos los árboles de la estación y puede elegir el menos saturado o forzar entrada con `force_add_vm`. Sin Junction, nadie toma esa decisión.

**En la topología actual esto se cumple naturalmente:** `len==1` solo llega a DOWN trees (nunca saturan) o a `BoardingLane` (siempre acepta). Los UP trees solo son alcanzables desde la Junction UP via `brain._handle_crossings`.

`network.process_transitions` tiene un guard defensivo: si `add_vehicle` devuelve `False`, llama `force_add_vehicle`. Esa rama **nunca debe activarse en operación normal** — si se activa, indica un error de topología.
