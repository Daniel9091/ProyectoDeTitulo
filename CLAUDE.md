# CLAUDE.md — Contexto de NSim para Claude

Este archivo es contexto persistente para Claude Code.
Describe el sistema, la arquitectura, los invariantes y el estado de implementación.
Actualizar cuando cambien contratos entre sistemas o cuando se complete un archivo vacío.

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
│   └── station.py          Estación: genera pasajeros, acumula demanda, gestiona andenes
│
├── tracks/         Segmentos de vía lineales — física del movimiento de VMs
│   ├── base.py             BaseTrack ABC: geometría y contrato común
│   ├── boarding_lane.py    Velocidad constante + abordaje de pasajeros
│   └── acceleration_tree.py  MRUA gravitacional (vacío — pendiente)
│
├── systems/        Sistemas de coordinación global — sin estado físico propio
│   ├── continuous_train.py Carril circular: slots, posiciones, etiquetas
│   ├── brain.py            Coordinador central: routing, demanda, colisiones (vacío)
│   ├── network.py          Grafo de tracks y adyacencia (vacío)
│   ├── demand_manager.py   Lógica de satisfacción de demanda (vacío)
│   ├── collision_predictor.py  Predicción anticipada de colisiones en tren (vacío)
│   ├── consumption_manager.py  Mecanismo de consumo de VMs (vacío)
│   ├── tree_selector.py    Selección del árbol óptimo para cada VM (vacío)
│   └── spatial_grid.py     Grid espacial para colisiones O(1) (vacío)
│
├── simulation/     Orquestación — ensambla todo y corre el loop (todos vacíos)
│   ├── simulation.py       Loop principal: llama brain.update(dt) cada frame
│   ├── simulation_builder.py  Construye el grafo de objetos inicial
│   ├── renderer.py         Pygame — visualización 3D
│   ├── event_handler.py    Eventos de teclado/mouse
│   ├── camera.py           Cámara 3D
│   ├── info_panel.py       Panel de métricas en pantalla
│   ├── vehicle_spawner.py  Crea VMs iniciales
│   ├── passenger_spawner.py  Llama station.update() para generar pasajeros
│   └── main.py             Entry point con pygame
│
├── config/
│   ├── constants.py        Todas las constantes físicas y de simulación
│   └── network_config.py   Configuración geométrica de la red (vacío)
│
└── tests/          Un archivo de test por cada archivo de objects/ y tracks/
```

**Regla de dependencias**: `objects` no importa nada del proyecto. `tracks` importa solo
`objects`. `systems` importa `objects` y `tracks`. `simulation` importa todo. Esta
jerarquía evita imports circulares.

---

## Flujo principal del loop de simulación

El loop no está implementado aún (`simulation/simulation.py` está vacío), pero el diseño
previsto basado en la arquitectura existente es:

```
simulation.py  →  brain.update(dt)  cada frame
                    │
                    ├─ continuous_train.advance(dt)        — mueve tail_x, O(1)
                    ├─ [para cada junction] detectar VMs que salen del carril
                    │    └─ network.tree_selector → best_tree.add_vehicle(vm, leftover)
                    ├─ [para cada track] track.update(dt)  — mueve VMs en árboles/lanes
                    │    └─ retorna lista de (vm, leftover_dt) completados
                    ├─ [para cada station] station.update(dt, current_time)
                    │    ├─ genera pasajeros nuevos
                    │    └─ acumula demanda de VMs
                    ├─ brain lee station.pending_demand
                    │    └─ marca slots en continuous_train (set_reservation / set_demand_supply)
                    └─ collision_predictor procesa entradas recientes a boarding lanes
```

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

### Reserva — `reserved_for_vm_id`
Sistema anticolicisón. El más prioritario de los tres.

- **SET**: VM entra a una boarding lane → Brain calcula con MRU/MRUA (velocidad del lane +
  aceleración del árbol de bajada + velocidad del tren) el slot objetivo → marca ese slot
  con el ID del VM → ajusta la aceleración del árbol para que el VM llegue exactamente ahí.
  Si el slot objetivo ya tiene un VM encima, se aplican reglas de prioridad para liberarlo
  (slots con VM + reserva activa tienen prioridad máxima por ser el sistema anticolicisón).
- **CLEAR**: VM llega al slot → `place_vm` limpia la reserva. O bien, el slot pasa el
  junction de salida sin que el VM haya llegado → Brain limpia reserva Y destino juntos.

### Destino — `destination_station_id`
Sistema de routing. Se anticipa antes de que el VM llegue al tren.

- **SET (anticipación)**: Al alcanzar BOARDING_COMMIT_PROGRESS en la boarding lane, Brain
  escribe en el slot ya reservado el destino de los pasajeros que el VM embarcó.
- **SET (confirmación)**: Cuando el VM llega físicamente al slot, `place_vm` confirma.
- **CLEAR**: `remove_vm` la limpia cuando el VM sale del slot hacia un árbol de subida.
- **Recovery**: Si el slot pasa el junction de salida sin que el VM haya llegado → Brain
  limpia tanto `destination_station_id` como `reserved_for_vm_id` del slot.

### Demanda — `demand_supply_for_station_id`
Sistema de taza. Permite a las estaciones asegurar VMs con antelación.

- **SET**: `station.pending_demand > 0` → Brain busca hacia atrás desde el junction de
  entrada de esa estación, en un rango que respeta el gap de saturación del árbol → marca
  el slot candidato con el ID de la estación.
- **CLEAR**: VM entra al árbol de subida de esa estación (promesa cumplida, `remove_vm`
  limpia). O slot pasa el junction sin que el VM haya entrado → Brain llama
  `station.on_commitment_broken()` y limpia la etiqueta.

**Contabilidad al entrar al árbol**: cuando un VM entra a cualquier árbol de subida de
estación X, Brain lee `demand_supply_for_station_id` del slot ANTES de llamar `remove_vm`:
- Si estaba marcado para X → no descuenta (ya contabilizado, Brain llama `on_vm_committed`)
- Si no estaba marcado → Brain llama `on_unplanned_vm_at_tree()` (descuenta 1, puede ir
  negativo — se autorregula)

**Límite de saturación**: cada AccelerationTree conoce su gap mínimo de slots (derivado de
`MIN_SAFE_DISTANCE` y la MRUA). Reserva y demanda respetan este gap al buscar candidatos.

---

## Estado de implementación (Mayo 2026)

### Completo con tests
- `objects/math3d.py` — Vector3
- `objects/types.py` — Enums
- `objects/passenger.py` — Ciclo de vida completo
- `objects/modular_vehicle.py` — Estado interno completo
- `objects/passenger_id_generator.py` — Contador global de IDs
- `tracks/base.py` — ABC con geometría
- `tracks/boarding_lane.py` — Física + abordaje

### Completo sin tests (pendientes)
- `objects/station.py`
- `systems/continuous_train.py`

### Vacío — pendiente de implementación
- `tracks/acceleration_tree.py`
- `systems/brain.py`
- `systems/network.py`
- `systems/demand_manager.py`
- `systems/collision_predictor.py`
- `systems/consumption_manager.py`
- `systems/tree_selector.py`
- `systems/spatial_grid.py`
- `simulation/` — todos los archivos
- `config/network_config.py`

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
Brain llama:  train.advance(dt)                       → cada frame, primero
Brain llama:  train.find_neartest_slot_to_belt_x(x)   → para encontrar slot en junction
Brain llama:  train.set_reservation(slot, vm_id)      → al comprometer un slot
Brain llama:  train.clear_reservation(slot)            → si el compromiso falla
Brain llama:  train.place_vm(vm, slot)                → cuando VM llega desde árbol DOWN
Brain llama:  train.remove_vm(slot)                   → cuando VM sale hacia árbol UP
Brain llama:  train.set_demand_supply(slot, station)  → marca slot para demanda
Brain llama:  train.set_destination(slot, station)    → registra destino del VM en slot
```

### Brain ↔ BaseTrack / AccelerationTree / BoardingLane
```
Brain llama:  track.update(dt)             → cada frame para cada track en la red
Brain recibe: [(vm, leftover_dt), ...]     → VMs que completaron el track
Brain llama:  next_track.add_vehicle(vm, leftover_dt=leftover)  → transición
```

---

## Dificultades de Claude para entender este proyecto

Esta sección es para calibrar qué contexto necesito al retomar el proyecto:

**Lo que me cuesta reconstruir sin leer el código:**
- El protocolo exacto de Brain ↔ ContinuousTrain (quién llama a quién en qué orden)
- Si `demand_supply_for_station_id` persiste o no después que el VM llega al slot (ver invariante 3)
- La diferencia entre "consumo" y "demanda" en el flujo de asignación de VMs

**Lo que necesito saber cuando los archivos vacíos estén implementados:**
- Cómo Network representa la topología (grafo de adyacencia, IDs de tracks)
- Cómo Brain decide qué slot reservar (¿lookback desde junction? ¿búsqueda bidireccional?)
- Cómo AccelerationTree recibe la aceleración ajustada por Brain para predicción de colisiones

**Marcadores `##?##` abiertos en el código:**
- `station.py` línea 57: `##?## Z` — pregunta sobre coordenada Z del parámetro `origin`
- `station.py` línea 111: `##?## en un futuro esto se puede externalizar` — sobre generación de IDs
Cuando estos sean resueltos, borrar el marcador y documentar la decisión aquí.

---

## Notas de desarrollo activo

- Tests de `station.py` y `continuous_train.py` están pendientes
- `continuous_train.py` fue completado en Mayo 2026 — primer sistema completo
- La variable `TRAIN_SPACING = TRAIN_VM_LENGTH + TRAIN_GAP` en `constants.py` es correcta:
  spacing es distancia entre centros, no entre bordes
- `BOARDING_COMMIT_PROGRESS = 0.5` significa que al llegar al 50% del lane el embarque es definitivo
- Los IDs de pasajeros se generan como `station_id * 100_000 + contador_local` para garantizar unicidad