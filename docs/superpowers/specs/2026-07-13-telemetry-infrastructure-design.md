# Diseño: Infraestructura de telemetría (Recorder + JSONL)

Fecha: 2026-07-13

## Contexto

NSim necesita registrar lo que pasa durante una corrida (pasajeros, VMs,
choques, decisiones de junctions, etiquetas, snapshots de estación) para
poder evaluar la efectividad del sistema y comparar contra el metro real.
Esto es un proyecto grande que se descompuso en sub-proyectos independientes:

1. **Infraestructura de telemetría (este documento)** — Recorder, formato
   de evento, ciclo de vida de la corrida, wiring.
2. Eventos de ciclo de vida de pasajero (spawn/board/arrive/evicted-con-pasajeros)
3. Odómetro de VM (`total_distance_traveled`)
4. Ciclo de vida de etiquetas de slot
5. Eventos de seguridad (choques belt/árbol, entradas forzadas, promesas rotas)
6. Snapshots periódicos de estación
7. Cálculo de summary agregado

Cada sub-proyecto siguiente agrega métodos nuevos a la clase `Recorder` y
puntos de llamada nuevos en el dominio, pero depende de que este documento
esté implementado primero.

## Objetivo de este sub-proyecto

Construir el `Recorder`, el formato de evento base, el layout de archivos
de una corrida, y el wiring (inyección por constructor) hacia los objetos
del dominio que van a emitir eventos en los sub-proyectos siguientes — sin
implementar todavía los eventos específicos de pasajero/choque/etc.
(`run_started`/`run_ended` son los únicos eventos concretos de este
sub-proyecto).

## Arquitectura

Paquete nuevo `telemetry/` al mismo nivel que `objects/`, `tracks/`,
`systems/`, `simulation/`. No importa nada del resto del proyecto — vive en
la capa más baja de la jerarquía de dependencias (igual que `objects/`),
porque `objects/station.py` y `tracks/*.py` necesitan poder importarlo sin
romper la regla de dependencias del proyecto (`objects` no importa nada del
proyecto; `tracks` importa solo `objects`; `systems` importa `objects` y
`tracks`; `simulation` importa todo).

```
telemetry/
    recorder.py       # Recorder, NullRecorder
```

Dos clases con la misma interfaz pública:

- `Recorder`: implementación real, escribe a un archivo JSONL.
- `NullRecorder`: mismos métodos, todos no-op. Se inyecta cuando la
  telemetría está desactivada — nadie que use un Recorder necesita ramas
  `if recorder is not None`.

## Formato de evento

Cada línea del `events.jsonl` es un objeto JSON con esta forma base:

```json
{"schema_version": 1, "seq": 42, "t": 812.35, "type": "run_started", ...}
```

- `schema_version`: entero, empieza en `1`. Permite parsear logs viejos
  correctamente si el esquema de un evento cambia en un sub-proyecto futuro.
- `seq`: contador monotónico interno del `Recorder`, incrementado en cada
  evento emitido — permite ordenar/deduplicar eventos que caen en el mismo
  `t` (varios eventos pueden ocurrir en el mismo tick).
- `t`: tiempo simulado (segundos), el mismo que usa `Brain.update`/`Station.update`.
- `type`: nombre del método del `Recorder` que generó el evento (ej.
  `"run_started"`), permite filtrar por tipo al analizar el JSONL.
- El resto de los campos son específicos de cada tipo de evento (definidos
  por cada sub-proyecto siguiente).

## Clase `Recorder`

```
class Recorder:
    def __init__(self, run_dir: Path, run_id: str, flush_every: int = 100)
    def run_started(self, t: float, config: dict) -> None
    def run_ended(self, t: float, summary: dict) -> None
    def close(self) -> None
```

- Mantiene un buffer en memoria (`list[dict]`) y un contador `seq`.
- Cada método público (`run_started`, `run_ended`, y los que se agreguen en
  sub-proyectos futuros) construye el dict del evento con los campos base
  (`schema_version`, `seq`, `t`, `type`) más los específicos, lo agrega al
  buffer, e incrementa `seq`.
- Cuando el buffer alcanza `flush_every` elementos, se escribe a disco
  (una línea JSON por elemento, `\n` al final) y se vacía el buffer.
- `close()` fuerza un flush del buffer pendiente (aunque no haya llegado a
  `flush_every`) y cierra el archivo. Es seguro llamarlo más de una vez.
- Serialización: usa un encoder JSON personalizado (`json.dumps(..., default=...)`)
  que convierte cualquier `Enum` a `.value` — necesario porque varios campos
  de eventos futuros van a ser `ModularVehicleState`/`TreeDirection`, que
  `json` no sabe serializar por defecto.

## Clase `NullRecorder`

Misma interfaz pública que `Recorder` (`run_started`, `run_ended`, `close`,
y cualquier método que se agregue después), todos los métodos son `pass`.
No abre ningún archivo, no mantiene buffer.

## Ciclo de vida de la corrida y layout de archivos

```
runs/
    <run_id>/
        events.jsonl    # una línea por evento; primera línea = run_started,
                         # última = run_ended
        summary.json     # copia del payload de run_ended (dict `summary`),
                         # para no tener que parsear todo events.jsonl
    index.jsonl           # una línea por corrida: {run_id, seed, scenario,
                           # started_at, events_path}, se le agrega una línea
                           # por cada corrida que se ejecuta
```

`run_id` se genera en `main.py` (no dentro de `Recorder`, para no atarlo al
reloj real y mantenerlo testeable con un `run_id` inyectado):

```
run_id = f"{scenario_name}_seed{seed}_{timestamp}"
# ej.: "inicial_seed42_20260713-143200"
```

`run_started(t=0.0, config=...)` recibe un dict con:
- `seed`, `scenario_name`
- todas las constantes públicas de `config/constants.py` (`{k: v for k, v
  in vars(constants).items() if not k.startswith('_')}`)
- parámetros de cada estación tal como están en `simulation_builder/inicial.py`
  (posiciones, `passenger_rate`, `vm_request_rate`, `destination_probabilities`,
  número de andenes)

Al terminar la corrida (normal o por excepción), `main.py`:
1. Construye el dict `summary` (en este sub-proyecto puede ser mínimo —
   `{"simulated_seconds": ...}` — los campos ricos se agregan en el
   sub-proyecto 7).
2. Llama `recorder.run_ended(t=sim.current_time, summary=summary)`.
3. Llama `recorder.close()`.
4. Escribe `summary.json` con el mismo dict `summary`.
5. Agrega una línea a `runs/index.jsonl` con el resumen de la corrida.

**Garantía ante crash**: los pasos 1-5 corren dentro de un bloque `finally`
que envuelve el loop principal de `main.py`, así una excepción no capturada
todavía dispara el flush final y el cierre del archivo antes de que el
proceso termine.

## Wiring — inyección por constructor

`Recorder`/`NullRecorder` se construye una vez en `main.py`, según una
constante `TELEMETRY_ENABLED` en `config/constants.py` (`True`/`False`), y
se pasa hacia abajo por parámetro:

```
main.py:      recorder = Recorder(run_dir, run_id) if TELEMETRY_ENABLED else NullRecorder()
              brain, stations = inicial.build(seed, recorder=recorder)

inicial.py:   build(seed, recorder) → create_station(..., recorder=recorder)
                                     → Brain(..., recorder=recorder)
                                     → ContinuousTrain(..., recorder=recorder)

station_factory.py: create_station(..., recorder) → Station(..., recorder=recorder)
                                                    → BoardingLane(..., recorder=recorder)
                                                    → AccelerationTree(..., recorder=recorder)
```

Cada clase guarda la referencia como `self._recorder` (mismo patrón que ya
usan con `self._logger`/`logger` a nivel de módulo). Este sub-proyecto solo
agrega el parámetro y el guardado — los sub-proyectos 2-6 son los que
agregan las llamadas reales a métodos del Recorder dentro de cada clase.

Archivos con firma de constructor modificada en este sub-proyecto:
`objects/station.py`, `tracks/boarding_lane.py`, `tracks/acceleration_tree.py`,
`systems/continuous_train.py`, `systems/brain.py`,
`simulation/station_factory.py` (`create_station`),
`simulation_builder/inicial.py` (`build`), `main.py`.

## Testing

Sin dependencia de pygame — testeable directo:
- `Recorder` escribe una línea JSON válida por evento, con los campos base
  correctos (`schema_version`, `seq` incremental, `t`, `type`).
- El buffer se vacía a disco al llegar a `flush_every`.
- `close()` vacía cualquier remanente del buffer y es seguro llamarlo dos veces.
- Un campo `Enum` en el payload de un evento se serializa como `.value`.
- `NullRecorder` no crea ningún archivo ni directorio.

Sigue el patrón de un archivo de test por archivo de código:
`tests/test_recorder.py`.

## Fuera de alcance (explícitamente, pertenece a sub-proyectos futuros)

- Cualquier evento específico de pasajero, VM, etiqueta, choque, junction o
  snapshot de estación — solo se define la infraestructura para soportarlos.
- El cálculo real de `summary` (KPIs de wait_time/travel_time/distancia/etc.)
  — en este sub-proyecto `summary` es un placeholder mínimo.
- Herramientas de análisis/consulta sobre `runs/` (notebooks, scripts de
  agregación, carga a DuckDB) — quedan fuera del código de NSim.