# CLAUDE.md — Contexto de NSim para Claude

Este archivo es contexto persistente para Claude Code.
Describe el sistema, la arquitectura, los invariantes y el estado de implementación.
Actualizar cuando cambien contratos entre sistemas o cuando se complete un archivo vacío.

**Navegación y estado del proyecto** → leer `docs/memory/INDEX.md` al inicio de cada sesión.

---

## ¿Qué es NSim?

NSim simula un sistema de transporte urbano basado en **vehículos modulares (VMs)** que
circulan por un carril inferior circular continuo y suben/bajan a estaciones mediante
árboles de aceleración gravitacional. El objetivo de la simulación es medir métricas de
servicio (tiempo de viaje de pasajeros, ocupación de VMs, demanda insatisfecha) para
evaluar la factibilidad del sistema.

NSim es la segunda versión del proyecto. Reemplaza a `../Sim` con arquitectura más limpia,
separación de responsabilidades explícita, y tests.

---

## Glosario

| Término | Significado |
|---|---|
| **VM** | Vehículo Modular — unidad de transporte individual con capacidad fija |
| **Slot** | Posición fija en el carril del tren; los slots no se mueven, los VMs los ocupan |
| **belt_x** | Coordenada 1D del carril circular, en metros desde el inicio `[0, total_length)` |
| **tail_x** | belt_x del slot 0 en el frame actual; avanza con el tren cada frame |
| **Junction** | Punto del carril donde un árbol conecta con el carril inferior (entrada/salida) |
| **Árbol de subida (UP)** | AccelerationTree que sube hacia la estación; la gravedad desacelera el VM |
| **Árbol de bajada (DOWN)** | AccelerationTree que baja desde la estación; la gravedad acelera el VM |
| **Boarding lane** | Segmento recto dentro de la estación donde los VMs recogen pasajeros |
| **Andén** | Una unidad dentro de una estación: `boarding_lane + up_tree + down_tree` |
| **Demanda** | Número de VMs que una estación necesita recibir (acumulador decimal) |
| **Reserva** | Slot bloqueado para un VM que está descendiendo y aún no llegó al carril |
| **Consumo** | Mecanismo por el que un VM ya en el carril es redirigido para satisfacer demanda urgente |
| **Commitment** | Punto en la boarding lane (BOARDING_COMMIT_PROGRESS) donde el embarque es definitivo |

---

## Arquitectura — carpetas y responsabilidades

```
NSim/
├── objects/        Entidades físicas — estado interno solamente, sin física ni routing
│   ├── math3d.py           Vector3: operaciones geométricas 3D
│   ├── types.py            Enums de estado (ModularVehicleState, PassengerState, etc.)
│   ├── modular_vehicle.py  VM: identidad, capacidad, pasajeros, destino, posición
│   ├── passenger.py        Pasajero: ciclo de vida y métricas de viaje
│   ├── passenger_id_generator.py  Contador global de IDs de pasajeros
│   └── station.py          Estación: genera pasajeros, acumula demanda, gestiona andenes
│
├── tracks/         Segmentos de vía lineales — física del movimiento de VMs
│   ├── base.py             BaseTrack ABC: geometría y contrato común
│   ├── boarding_lane.py    Velocidad constante + abordaje de pasajeros
│   ├── acceleration_tree.py  MRUA gravitacional; calcula su propia aceleración desde geometría
│   └── junction.py         Punto de conexión belt↔árboles, routing, burst_capacity
│
├── systems/        Sistemas de coordinación global — sin estado físico propio
│   ├── continuous_train.py Carril circular: slots, etiquetas, advance() con crossing detection
│   ├── network.py          Topología, update_all_tracks, process_transitions
│   └── brain.py            Coordinador central: routing, demanda, colisiones (COMPLETO)
│
├── simulation/     Orquestación y visualización
│   ├── station_factory.py  Construye una estación completa con geometría 3D automática
│   ├── simulation.py       Simulation.step(dt) / run_headless(n_ticks) — wrapper sobre Brain
│   ├── camera.py           Cámara 3D con proyección perspectiva (yaw/pitch/FOV, mouse look)
│   ├── renderer.py         Pygame — wireframe 3D de VMs, árboles, estaciones, HUD
│   └── inspector.py        (click-to-inspect de VMs y estaciones)
│
├── simulation_builder/     Escenarios — cada archivo construye una red completa
│   ├── inicial.py          Escenario base: 3 estaciones (S2 con 3 andenes)
│   └── molde.py            Template con `...` para copiar al crear un escenario nuevo
│
├── config/
│   └── constants.py        Todas las constantes físicas y de simulación
│
├── main.py         Entry point pygame (raíz de NSim, no dentro de simulation/)
│
└── tests/          Un archivo de test por cada archivo de objects/, tracks/, systems/, simulation/
```

**Regla de dependencias**: `objects` no importa nada del proyecto. `tracks` importa solo
`objects`. `systems` importa `objects` y `tracks`. `simulation` y `simulation_builder`
importan todo. `main.py` importa `simulation_builder` y `simulation`. Esta jerarquía evita
imports circulares.

**Archivos que ya NO existen** (fueron absorbidos o descartados):
`systems/demand_manager.py`, `systems/collision_predictor.py`, `systems/consumption_manager.py`
(absorbidos en Brain), `config/network_config.py`, `systems/tree_selector.py`, `systems/spatial_grid.py`.

---

## Flujo principal del loop de simulación

Implementado en `systems/brain.py` (`Brain.update`) y verificado con 353 tests y ejecución
real vía `main.py`. El loop es:

```
TICK N — brain.update(dt):

continuous_train.advance(dt)
→ mueve tail_x, retorna list[(slot_idx, station_id, leftover_dt)]
→ O(junctions). Limitación: TRAIN_SPEED * dt < TRAIN_SPACING debe cumplirse.

network.update_all_tracks(dt)   ← TRACKS PRIMERO, antes del junction routing
→ Avanza AccelerationTrees y BoardingLanes para todos los tracks
→ Solo recolecta completions [(vm, track_id, leftover_dt)], no transfiere

network.process_transitions(completions)
→ len==1: transición mecánica, Network transfiere directamente
→ len>1:  decisión de Brain → devuelve decisions
→ len==0: DOWN tree terminal → devuelve belt_placements

Brain procesa crossings del paso 1   ← JUNCTION ROUTING DESPUÉS de update_all_tracks
→ Lee etiquetas del slot (destination, demand_supply)
→ Si VM sube: train.remove_vm(slot) → junction_up.add_vm(vm, leftover_dt)
→ VMs transferidos NO se mueven este tick (leftover banqueado en initial_distance)

Brain ejecuta decisions del paso 3
→ Para cada (vm, [next_ids], leftover): elige next_id → track.add_vehicle(vm, leftover)

Brain ejecuta belt_placements del paso 3
→ Para cada (vm, leftover, station_id): train.place_vm(vm, pre_reserved_slot)

station.update(dt, current_time)
→ Genera pasajeros, acumula demanda, avanza caminantes

Brain toma decisiones para ticks futuros
→ Lee station.pending_demand → marca slots de demanda/reserva
→ VMs que commitieron en boarding lane → reserva slot DOWN + set_vehicle_acceleration
→ Compromisos rotos → station.on_commitment_broken()
→ Ajuste de aceleraciones para anti-colisión en DOWN trees activos

```

CRÍTICO — por qué tracks van ANTES que el junction routing (paso 2 antes de paso 4):
Si Brain transfiriera VMs a UP trees (paso 4) ANTES de update_all_tracks (paso 2),
el VM recibiría `advance(leftover_dt)` como initial_distance al entrar + `advance(dt)`
de tree.update() en el mismo tick = un frame completo de movimiento de más.
Con el orden correcto, los VMs transferidos en paso 4 esperan al siguiente tick.

El orden importa: el tren avanza ANTES de procesar salidas para que los slots calculados
correspondan a posiciones actualizadas.

---

## Invariantes de diseño (decisiones no obvias)

**1. Slots son posiciones fijas, no VMs**
Los slots no se mueven. `tail_x` avanza y los slots "parecen moverse" porque su posición
3D se recalcula desde `tail_x` cada vez que se consulta. Un slot puede estar: libre,
reservado (VM descendiendo), ocupado (VM presente) o marcado para demanda.

**2. Un slot no puede tener VM y reserva simultáneamente**
El flujo es: libre → reservado (Brain lo reserva) → ocupado (VM llega) → libre (VM sale).
`place_vm` limpia la reserva. Un slot ocupado NUNCA tiene `reserved_for_vm_id != None`.

**3. `demand_supply_for_station_id` persiste después que el VM llega al slot**
Cuando un VM llega a su slot (`place_vm`), la etiqueta `demand_supply_for_station_id`
se mantiene para que Brain sepa que ese VM ya está asignado a esa estación y lo saque
en el junction correcto. La limpia `remove_vm` cuando el VM sale del carril.

**4. La estación no mueve VMs ni conoce Brain directamente**
`station.update()` acumula demanda en `_vm_demand_accumulator`. Brain lee
`station.pending_demand` y decide qué hacer. La estación solo expone la demanda y
notifica via `on_vm_committed()` / `on_commitment_broken()` / `on_unplanned_vm_at_tree()`.

**5. El pasajero no se embarca a sí mismo**
`BoardingLane.add_vehicle()` toma pasajeros de la cola y llama `passenger.start_boarding()`.
`BoardingLane.update()` llama `passenger.complete_boarding(vehicle_id)` al alcanzar
BOARDING_COMMIT_PROGRESS. El pasajero solo registra estados.

**6. `distance` en tracks, NO `progress`**
Los dicts de `self.vehicles` guardan `distance` en metros, no `progress` normalizado.
`get_progress()` calcula `distance / length` cuando se necesita. Esto evita acumulación
de error flotante por divisiones repetidas cada frame.

**7. `leftover_dt` en transiciones entre tracks**
Cuando un VM completa un track en el frame, `update()` retorna `(vm, leftover_dt)`.
El caller usa ese `leftover_dt` para llamar `add_vehicle(vm, leftover_dt=...)` en el
siguiente track, de modo que el VM no "pierde" tiempo de movimiento en la transición.

**8. Andenes en round-robin**
`station._select_anden()` usa `next_anden_index % len(active_andenes)` para distribuir
pasajeros equitativamente entre andenes activos. El índice se incrementa en cada asignación.

**9. Grupos de pasajeros por destino en BoardingLane**
Los pasajeros esperan agrupados por `destination_station_id`. Cuando llega un VM, aborda
el grupo cuyo pasajero más antiguo lleva más tiempo esperando (`spawn_time` mínimo). El VM
aborda hasta `capacity` pasajeros de ese grupo solamente (todos van al mismo destino).

---

## Sistema de Etiquetas de Slots

Cada slot tiene 3 etiquetas gestionadas exclusivamente por Brain. **Son independientes y no
excluyentes** — un slot puede tener las 3 activas al mismo tiempo. Al buscar candidatos por
rango, Brain debe preferir slots que ya tengan otras etiquetas activas: maximiza la utilidad
de los VMs que ya van a entrar y protege la saturación de los árboles.

### Reserva — `reserved_station_id`
Sistema anticolicisón. Almacena `station_id | None` (NO vm_id — Brain usa `_reserved_slots: dict[int,int]` para vm_id→slot).

- **SET**: VM hace commit en boarding lane → Brain calcula tiempo (lane + DOWN tree) → encuentra qué slot estará en junction_down en ese momento → marca ese slot con el `station_id` de la estación → ajusta `vm.reserved_tree_acceleration` para que el VM llegue exactamente ahí.
- **CLEAR**: `place_vm` limpia la reserva cuando el VM aterriza en el slot.
- **Junction UP behavior**: si `reserved_station_id == station_id` → try `add_vm`; si rechaza → Brain llama `force_add_vm` en el **mismo frame** (el sistema de reserva garantiza entrada).

### Destino — `destination_station_id`
Sistema de routing. Se anticipa antes de que el VM llegue al tren.

- **SET (anticipación)**: Al alcanzar BOARDING_COMMIT_PROGRESS en la boarding lane, Brain
  escribe en el slot ya reservado el destino de los pasajeros que el VM embarcó.
- **SET (confirmación)**: Cuando el VM llega físicamente al slot, `place_vm` confirma.
- **CLEAR**: `remove_vm` la limpia cuando el VM sale del slot hacia un árbol de subida.
- **Recovery**: Si el slot pasa el junction de salida sin que el VM haya llegado → Brain
  limpia tanto `destination_station_id` como `reserved_station_id` del slot.

### Demanda — `demand_station_id`
Sistema de taza. Permite a las estaciones asegurar VMs con antelación.

- **SET**: `station.pending_demand > 0` → Brain busca hacia atrás desde el junction de
  entrada de esa estación, en un rango que respeta el gap de saturación del árbol → marca
  el slot candidato con el ID de la estación.
- **CLEAR**: VM entra al árbol de subida de esa estación (promesa cumplida, `remove_vm`
  limpia). O slot pasa el junction sin que el VM haya entrado → Brain llama
  `station.on_commitment_broken()` y limpia la etiqueta.
- **Junction UP behavior**: si `demand_station_id == station_id` → try `add_vm`; si rechaza → `on_commitment_broken` + VM sigue en belt.

**Contabilidad al entrar al árbol**: cuando un VM entra a cualquier árbol de subida de
estación X, Brain lee `demand_station_id` del slot ANTES de llamar `remove_vm`:
- Si estaba marcado para X → no descuenta (ya contabilizado vía `on_vm_committed`)
- Si no estaba marcado → Brain llama `on_unplanned_vm_at_tree()` (descuenta 1, puede ir
  negativo — se autorregula)

**Límite de saturación**: cada AccelerationTree conoce su gap mínimo de slots (derivado de
`MIN_SAFE_DISTANCE` y la MRUA). Reserva y demanda respetan este gap al buscar candidatos.

---

## Estado de implementación (Agosto 2026) — 353 tests, todos verdes

### Completo con tests
- `objects/` — math3d, types, passenger, modular_vehicle, passenger_id_generator, station
- `tracks/` — base, boarding_lane, acceleration_tree, junction
- `systems/` — continuous_train, network, brain
- `simulation/station_factory.py`

### Completo y funcional, verificado corriendo (sin test automatizado)
- `simulation_builder/inicial.py` — escenario corre indefinidamente sin crashear
- `simulation/simulation.py`, `camera.py`, `renderer.py`, `main.py` — pygame end-to-end

### Vacío — no implementado, no bloqueante
- `simulation/info_panel.py` (eliminado — reemplazado por inspector.py)
- `simulation/event_handler.py`, `vehicle_spawner.py`, `passenger_spawner.py` (nunca se crearon; sus responsabilidades quedaron cubiertas por camera.py/renderer.py y station.update()/density inicial)

---

## Bugs resueltos (Mayo 2026)

Todos los bugs fueron corregidos en esta sesión:
- `station.py`: 5 typos en nombres de métodos (AttributeError en runtime) + 1 property mal nombrada + ortografía de `_accumulate_vm_demand`
- `main.py`: `VehicleState` → `ModularVehicleState`
- `continuous_train.py`: docstring con fórmula incorrecta en `get_slot_belt_x`
- `test_math3d.py`: `normal_case` sin prefijo `test_` (pytest nunca lo descubría)
- `test_boarding_lane.py`: assertion verificaba destino `1` pero pasajero iba a destino `2`
- `test_modular_vehicle.py`: `assert vm` siempre True → cambiado a `assert vm.has_destination`
- `test_base.py`: `MinimalTrack.remove_vehicle(vehicle)` violaba contrato del ABC → ahora toma `vehicle_id: int`

---

## Contratos entre sistemas (lo que Brain necesita saber)

### Brain ↔ Station
```
Brain lee:    station.pending_demand          → int (parte entera del acumulador)
Brain llama:  station.on_vm_committed()       → cuando reserva un slot para esa estación
Brain llama:  station.on_commitment_broken()  → cuando el VM comprometido fue rechazado
Brain llama:  station.on_unplanned_vm_at_tree() → cuando un VM no marcado subió al árbol
```

### Brain ↔ ContinuousTrain
```
Brain llama:  train.advance(dt)                        → list[(slot_idx, station_id, leftover_dt)]
Brain llama:  train.find_neartest_slot_to_belt_x(x)    → (slot_idx, distancia)
Brain llama:  train.set_reservation(slot, station_id)  → al comprometer un slot (almacena station_id, no vm_id)
Brain llama:  train.clear_reservation(slot)             → si el compromiso falla
Brain llama:  train.place_vm(vm, slot)                 → cuando VM llega desde árbol DOWN
Brain llama:  train.remove_vm(slot)                    → cuando VM sale hacia árbol UP (retorna el vm)
Brain llama:  train.set_demand_supply(slot, station)   → marca slot para demanda (→ demand_station_id)
Brain llama:  train.set_destination(slot, station)     → registra destino del VM en slot
```

### Brain ↔ Network
```
Brain llama:  network.update_all_tracks(dt)            → list[(vm, track_id, leftover_dt)]
Brain llama:  network.process_transitions(completions) → (decisions, belt_placements)
                decisions:       list[(vm, [next_ids], leftover_dt)]   — Brain elige qué track
                belt_placements: list[(vm, leftover_dt, station_id)]   — Brain llama train.place_vm
Brain llama:  network.get_junction_up(station_id)      → Junction | None
Brain llama:  network.get_junction_down(station_id)    → Junction | None
Brain llama:  network.get_all_station_ids()            → list[int]
Brain llama:  junction.add_vm(vm, leftover_dt)         → primer intento para todos los VMs
Brain llama:  junction.force_add_vm(vm, leftover_dt)   → mismo frame, solo para VMs con reserved_station_id (forzado si add_vm rechaza)
Brain llama:  tree.set_vehicle_acceleration(vm_id, a)  → ajusta aceleración DOWN para reserva de slot
```

---

## Dificultades de Claude para entender este proyecto

Esta sección es para calibrar qué contexto necesito al retomar el proyecto:

**Lo que me cuesta reconstruir sin leer el código:**
- El orden exacto de pasos dentro del tick de Brain: `advance → update_all_tracks → process_transitions → handle_crossings → handle_decisions → handle_belt_placements → station.update → process_reservations → process_demand`
- Que `reserved_station_id` almacena `station_id` (no vm_id) — Brain mantiene `_reserved_slots: dict[int,int]` (vm_id→slot_idx) por separado
- Qué ocurre cuando `junction.add_vm` rechaza: solo `reserved_station_id` fuerza entrada en el mismo frame (`force_add_vm`); `destination_station_id` y `demand_station_id` son condicionales (VM se queda en belt si rechaza)
- Que `AccelerationTree` calcula su propia `base_acceleration` desde `dz/length * GRAVITY` — NO se pasa como parámetro. Un árbol con `dz=0` lanza `ValueError` (fail-fast, no degrada a aceleración 0).
- Que `JUNCTION_DEPTH` en un escenario NO es arbitrario: debe cumplir `dz = (TRAIN_SPEED²-BOARDING_LANE_SPEED²)/(2·GRAVITY)` para que el VM realmente alcance BOARDING_LANE_SPEED al final del árbol.

**Marcadores `##?##` abiertos en el código:** ninguno pendiente conocido a julio 2026.

---

## Bugs resueltos (Junio 2026)

Adicionalmente a los bugs de Mayo 2026 (ver historial):
- `acceleration_tree.py`: leftover_dt usaba fórmula lineal `remaining/old_velocity` → corregido a MRUA exacto `(-v + sqrt(v²+2a·r))/a`
- `acceleration_tree.py`: `set_vehicle_acceleration()` clampeaba al rango de comodidad → corregido a solo advertir, sin clamp
- `acceleration_tree.py`: agregado parámetro `station_id: int | None` necesario para `network.process_transitions()`
- `test_acceleration_tree.py`: dos tests de "clamp" actualizados para reflejar nuevo comportamiento (solo warning)
- `test_acceleration_tree.py`: valor esperado en `test_update_returns_leftover_dt` corregido de 1.0 a 1.146

## Bugs resueltos (Julio 2026)

- `acceleration_tree.py`: **refactor arquitectónico** — `base_acceleration` ya no es parámetro del constructor. Se calcula internamente en `_compute_effective_acceleration()` desde `dz = |end_pos.z - start_pos.z|` y `GRAVITY`. Si `dz <= 0` lanza `ValueError` (antes: `station_factory.py` calculaba la física y se la pasaba — violación de responsabilidad).
- `brain.py` — `_would_saturate`: usaba `count >= N`, lo que bloqueaba SIEMPRE el primer VM en estaciones con `burst_capacity=1` (1 andén). Corregido a `count > N`.
- `brain.py` — `_make_reservation`: signo invertido en `T_target = T_total + raw_offset * (...)`. Corregido a `-`. Con el signo malo, los VMs llegaban sistemáticamente desfasados de su slot reservado (offset de hasta -10 slots observado en simulación real).
- `simulation_builder/inicial.py`: `JUNCTION_DEPTH` debe cumplir `dz = (TRAIN_SPEED²-BOARDING_LANE_SPEED²)/(2·GRAVITY)` — un valor puesto sin verificar esta relación deja a los VMs congelados dentro del árbol o sin desacelerar lo suficiente antes del boarding lane.

## Notas de desarrollo activo

- `TRAIN_SPACING = TRAIN_VM_LENGTH + TRAIN_GAP` — spacing es distancia entre centros, no entre bordes
- `BOARDING_COMMIT_PROGRESS = 0.5` — al 50% del lane el embarque es definitivo
- IDs de pasajeros: usa `PassengerIdGenerator` (contador global), no el esquema `station_id * 100_000`
- `ACCEL_RANGE_MIN/MAX` son de comodidad del pasajero (advertencia), no límites duros — Brain puede superar el rango en emergencias anticolicisón
- `TREE_ACCELERATION` YA NO ES una constante global — cada `AccelerationTree` calcula la suya desde su geometría (ver Bugs resueltos Julio 2026). Solo sobrevive como constante local en algunos archivos de test.

---

## Brain — Diseño Verificado (Junio 2026)

> Plan completo en `/home/danielguzman/.claude/plans/indexed-riding-breeze.md`

### Estado del objeto

```python
class Brain:
    _train: ContinuousTrain
    _network: Network
    _stations: dict[int, Station]
    _reserved_slots: dict[int, int]   # vm_id → slot_idx (reservas activas pendientes de belt_placement)
```

### Loop — 8 pasos, orden invariante

```
1. crossings = train.advance(dt)
2. completions = network.update_all_tracks(dt)
3. decisions, belt_placements = network.process_transitions(completions)
4. _handle_crossings(crossings)
5. _handle_decisions(decisions)
6. _handle_belt_placements(belt_placements)
7. station.update(dt, current_time)  # para cada estación
8a. _process_reservations()
8b. _process_demand()
```

**Invariante de orden**: tracks UP (paso 2) ANTES que junction routing (paso 4) — evita doble advance.
**Invariante de orden**: station.update (paso 7) ANTES que demand/reservations (paso 8) — Brain lee `pending_demand` actualizado.
**Invariante de orden**: reservations (8a) ANTES que demand (8b) — orden semántico: las reservas son compromisos ya contraídos (VM en boarding lane), la demanda es especulación sobre el futuro. NOTA: en el código actual _make_reservation NO llama on_vm_committed(); ambos ordenes producen el mismo call_count. El ordenamiento se mantiene por claridad semántica y porque si en el futuro _make_reservation adquiriera on_vm_committed(), el orden ya correcto evitaría doble descuento.

### Crossing handler — 3 comportamientos (por etiqueta)

Para cada `(slot_idx, station_id, leftover_dt)` en crossings donde el slot tiene un VM:

| Condición | Acción |
|---|---|
| `reserved_station_id == S` | `add_vm` → si rechaza: `force_add_vm` (mismo frame) |
| `destination_station_id == S` | `add_vm` → si rechaza: VM pasa de largo (no force) |
| `demand_station_id == S` | `add_vm` → si rechaza: `on_commitment_broken` + `clear_demand_station_id`, VM pasa |
| ninguna etiqueta == S | VM pasa de largo sin acción |

`remove_vm()` limpia `destination_station_id` y `demand_station_id` automáticamente.

### Sistema de reserva — matemáticas

```
T_lane = distancia_restante / BOARDING_LANE_SPEED
T_tree_std = (TRAIN_SPEED - BOARDING_LANE_SPEED) / down_tree.base_acceleration
T_total = T_lane + T_tree_std

future_tail_x = (train.tail_x + TRAIN_SPEED * T_total) % train.total_length
relative = (junction_down.belt_x - future_tail_x + train.total_length) % train.total_length
target_idx = round(relative / TRAIN_SPACING) % train.max_slots
```

Ajuste por offset del slot elegido `best_slot`:
```
raw_offset = (best_slot - target_idx + max_slots//2) % max_slots - max_slots//2
T_target = T_total - raw_offset * (TRAIN_SPACING / TRAIN_SPEED)
T_tree_adj = T_target - T_lane
a = 2.0 * (tree_length - BOARDING_LANE_SPEED * T_tree_adj) / T_tree_adj**2
```

CRÍTICO — el signo de `raw_offset` en `T_target`: un slot que está ADELANTE del target
(raw_offset > 0) llega a junction_down ANTES en el tiempo → el VM debe apurarse → `T_target`
debe ser MENOR que `T_total`. Por eso es RESTA, no suma. (Bug real corregido en julio 2026 —
con el signo `+`, los VMs llegaban sistemáticamente desfasados de su slot.)

### Búsqueda en rango — constantes y prioridades

`SLOT_SEARCH_RANGE_RESERVATION = 40` — ±20 slots (reserva necesita margen amplio para ajustar timing)
`SLOT_SEARCH_RANGE_DEMAND = 10` — 10 slots atrás solamente.

Prioridades para reserva (mejor primero):
1. Slot con etiqueta de la misma estación (dest o demand == S), no saturaría
2. Slot vacío sin reserva, no saturaría
3. VM sin destino conflictivo, no saturaría
4. VM con dest diferente, no saturaría (log WARNING — pasajeros se bajan en estación equivocada)
5. Minimiza saturación (log CRITICAL)

### Chequeo de saturación

`_would_saturate(junction, candidate, station_id)`:
- Lee `junction.burst_capacity` (N) y `junction.burst_window` (G)
- Cuenta slots ya marcados para S en ventana de tamaño G alrededor del candidato
- Retorna `True` si alguna sub-ventana de tamaño G ya tiene MÁS de N slots marcados (`count > N`,
  no `>=` — con `>=`, N=1 (estación de 1 andén) bloqueaba siempre el primer VM: bug real
  corregido en julio 2026)