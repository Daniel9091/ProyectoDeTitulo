# Telemetry Infrastructure Implementation Plan

> **Nota de flujo:** Daniel escribe el código él mismo — el asistente entrega
> el contenido de cada archivo como texto, nunca usa Edit/Write sobre
> archivos del proyecto. Este documento es referencia de qué se construyó y
> por qué.

**Goal:** Construir el `Recorder`/`NullRecorder`, el formato de evento
JSONL, el ciclo de vida de una corrida (`runs/<run_id>/`), y el wiring por
constructor hacia los objetos del dominio que emitirán eventos en
sub-proyectos futuros.

**Architecture:** Paquete nuevo `telemetry/` (sin dependencias del resto
del proyecto, mismo nivel que `objects/`). `Recorder` bufferiza eventos en
memoria y los vacía a `events.jsonl` cada `flush_every` eventos y en
`close()`. Se inyecta por constructor en `Station`, `BoardingLane`,
`AccelerationTree`, `ContinuousTrain` y `Brain`, construido una sola vez en
`main.py` según `TELEMETRY_ENABLED`.

**Tech Stack:** Python 3 estándar (`json`, `pathlib`, `enum`) — sin
dependencias nuevas.

## Global Constraints

- No implementar eventos específicos de pasajero/VM/etiqueta/choque/snapshot
  en este plan — son sub-proyectos futuros (ver spec, sección "Fuera de
  alcance").
- `telemetry/` no importa nada de `objects/`, `tracks/`, `systems/`,
  `simulation/` — solo stdlib.
- Spec de referencia:
  `docs/superpowers/specs/2026-07-13-telemetry-infrastructure-design.md`.

---

## Task 1: `Recorder` y `NullRecorder`

**Files:**
- Create: `telemetry/__init__.py` (vacío, igual que `objects/__init__.py`)
- Create: `telemetry/recorder.py`
- Test: `tests/test_recorder.py`

**Interfaces:**
- Produce: `class Recorder` con `__init__(self, run_dir: Path, run_id: str, flush_every: int = 100)`,
  `run_started(self, t: float, config: dict) -> None`,
  `run_ended(self, t: float, summary: dict) -> None`,
  `close(self) -> None`
- Produce: `class NullRecorder` con la misma interfaz pública, todos no-op

- [ ] **Step 1: Escribir los tests**

```python
# tests/test_recorder.py
import json
from pathlib import Path
from enum import Enum

from telemetry.recorder import Recorder, NullRecorder


class _FakeEnum(Enum):
    FOO = "foo"


def _read_lines(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def test_run_started_writes_base_fields_on_close(tmp_path):
    recorder = Recorder(run_dir=tmp_path, run_id="test_run")
    recorder.run_started(t=0.0, config={"seed": 42})
    recorder.close()

    lines = _read_lines(tmp_path / "events.jsonl")
    assert len(lines) == 1
    event = lines[0]
    assert event["schema_version"] == 1
    assert event["seq"] == 0
    assert event["t"] == 0.0
    assert event["type"] == "run_started"
    assert event["config"] == {"seed": 42}


def test_seq_increments_across_events(tmp_path):
    recorder = Recorder(run_dir=tmp_path, run_id="test_run")
    recorder.run_started(t=0.0, config={})
    recorder.run_ended(t=10.0, summary={})
    recorder.close()

    lines = _read_lines(tmp_path / "events.jsonl")
    assert [e["seq"] for e in lines] == [0, 1]
    assert [e["type"] for e in lines] == ["run_started", "run_ended"]


def test_flushes_to_disk_at_threshold(tmp_path):
    recorder = Recorder(run_dir=tmp_path, run_id="test_run", flush_every=3)
    events_path = tmp_path / "events.jsonl"

    recorder.run_started(t=0.0, config={})
    recorder.run_started(t=1.0, config={})
    assert not events_path.exists()  # todavia no llega al umbral

    recorder.run_started(t=2.0, config={})  # 3er evento -> flush
    assert len(_read_lines(events_path)) == 3


def test_close_flushes_pending_buffer_below_threshold(tmp_path):
    recorder = Recorder(run_dir=tmp_path, run_id="test_run", flush_every=100)
    recorder.run_started(t=0.0, config={})
    recorder.close()

    assert len(_read_lines(tmp_path / "events.jsonl")) == 1


def test_close_is_safe_to_call_twice(tmp_path):
    recorder = Recorder(run_dir=tmp_path, run_id="test_run")
    recorder.run_started(t=0.0, config={})
    recorder.close()
    recorder.close()  # no debe lanzar excepcion

    assert len(_read_lines(tmp_path / "events.jsonl")) == 1


def test_enum_field_serializes_to_its_value(tmp_path):
    recorder = Recorder(run_dir=tmp_path, run_id="test_run")
    recorder.run_started(t=0.0, config={"mode": _FakeEnum.FOO})
    recorder.close()

    lines = _read_lines(tmp_path / "events.jsonl")
    assert lines[0]["config"]["mode"] == "foo"


def test_null_recorder_creates_no_files(tmp_path):
    recorder = NullRecorder()
    recorder.run_started(t=0.0, config={"seed": 42})
    recorder.run_ended(t=10.0, summary={})
    recorder.close()

    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `pytest tests/test_recorder.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'telemetry'`

- [ ] **Step 3: Crear `telemetry/__init__.py` vacío**

Archivo vacío (0 bytes), igual que `objects/__init__.py`.

- [ ] **Step 4: Implementar `telemetry/recorder.py`**

```python
"""
recorder.py — Registro estructurado de eventos de una corrida de NSim.

Responsabilidades:
    - Serializar eventos a JSONL con campos base consistentes
      (schema_version, seq, t, type)
    - Bufferizar en memoria y volcar a disco cada N eventos y al cerrar

Lo que NO hace:
    - No sabe qué eventos existen a nivel de dominio (pasajero, VM, choque,
      etc.) — esos se agregan como métodos nuevos en sub-proyectos futuros
    - No decide si la telemetría está activa — main.py elige entre Recorder
      y NullRecorder según config/constants.py:TELEMETRY_ENABLED
"""
import json
from enum import Enum
from pathlib import Path

SCHEMA_VERSION = 1


def _json_default(obj):
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Objeto no serializable: {type(obj)!r}")


class Recorder:
    """
    Escribe eventos estructurados a runs/<run_id>/events.jsonl.

    Uso:
        recorder = Recorder(run_dir=Path("runs/inicial_seed42_..."), run_id="...")
        recorder.run_started(t=0.0, config={...})
        ...
        recorder.run_ended(t=sim.current_time, summary={...})
        recorder.close()
    """

    def __init__(self, run_dir: Path, run_id: str, flush_every: int = 100):
        self._run_dir = Path(run_dir)
        self._run_id = run_id
        self._flush_every = flush_every
        self._buffer: list[dict] = []
        self._seq = 0
        self._closed = False

        self._run_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = self._run_dir / "events.jsonl"
        self._file = open(self._events_path, "a", encoding="utf-8")

    def run_started(self, t: float, config: dict) -> None:
        self._emit("run_started", t, {"config": config})

    def run_ended(self, t: float, summary: dict) -> None:
        self._emit("run_ended", t, {"summary": summary})

    def close(self) -> None:
        if self._closed:
            return
        self._flush()
        self._file.close()
        self._closed = True

    # ── internos ─────────────────────────────────────────────────────────

    def _emit(self, event_type: str, t: float, fields: dict) -> None:
        event = {
            "schema_version": SCHEMA_VERSION,
            "seq": self._seq,
            "t": t,
            "type": event_type,
            **fields,
        }
        self._seq += 1
        self._buffer.append(event)
        if len(self._buffer) >= self._flush_every:
            self._flush()

    def _flush(self) -> None:
        if not self._buffer:
            return
        for event in self._buffer:
            self._file.write(json.dumps(event, default=_json_default) + "\n")
        self._file.flush()
        self._buffer.clear()


class NullRecorder:
    """
    Misma interfaz publica que Recorder, sin efecto alguno. Se usa cuando
    TELEMETRY_ENABLED es False — evita ramas `if recorder:` en el dominio.
    """

    def run_started(self, t: float, config: dict) -> None:
        pass

    def run_ended(self, t: float, summary: dict) -> None:
        pass

    def close(self) -> None:
        pass
```

- [ ] **Step 5: Correr y verificar que pasan**

Run: `pytest tests/test_recorder.py -v`
Expected: PASS (8 tests)

- [ ] **Step 6: Commit**

```bash
git add telemetry/__init__.py telemetry/recorder.py tests/test_recorder.py
git commit -m "feat: Recorder y NullRecorder para telemetria de corridas"
```

---

## Task 2: Constante `TELEMETRY_ENABLED`

**Files:**
- Modify: `config/constants.py`

**Interfaces:**
- Produce: `TELEMETRY_ENABLED: bool`

- [ ] **Step 1: Agregar la constante**

Al final de `config/constants.py`, agregar:

```python

# CTE. TELEMETRIA

TELEMETRY_ENABLED = True   # False -> main.py usa NullRecorder, no se escribe nada a runs/
```

- [ ] **Step 2: Verificación**

Run: `python3 -c "from config.constants import TELEMETRY_ENABLED; print(TELEMETRY_ENABLED)"`
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add config/constants.py
git commit -m "feat: agregar TELEMETRY_ENABLED a constants"
```

---

## Task 3: Wiring por constructor — `Station`, `BoardingLane`, `AccelerationTree`

**Files:**
- Modify: `objects/station.py:76-97`
- Modify: `tracks/boarding_lane.py:38-43`
- Modify: `tracks/acceleration_tree.py:75-91`
- Test: `tests/test_station.py`, `tests/test_boarding_lane.py`, `tests/test_acceleration_tree.py`
  (agregar el parámetro a las construcciones existentes en esos tests)

**Interfaces:**
- Consume: ninguna clase de `telemetry` directamente en la firma (se acepta
  cualquier objeto con la interfaz de `Recorder`/`NullRecorder`, sin import
  — evita que `objects/` y `tracks/` dependan de `telemetry/` en tiempo de
  import, aunque la regla de dependencias lo permitiría; se prefiere no
  acoplar el tipo para mantener estas clases agnósticas de qué es un
  Recorder)
- Produce: cada clase guarda `self._recorder` para que sub-proyectos
  futuros lo usen

- [ ] **Step 1: Modificar `Station.__init__`**

En `objects/station.py`, el constructor pasa de:

```python
    def __init__(
        self,
        station_id:                 int,
        origin:                     Vector3,
        dimensions:                 StationDimensions,
        passenger_rate:             float,
        destination_probabilities:  dict,
        vm_request_rate:            float,
        platforms:                  list,
        rng:                        random.Random,
        id_generator:               PassengerIdGenerator,
    ):
```

a:

```python
    def __init__(
        self,
        station_id:                 int,
        origin:                     Vector3,
        dimensions:                 StationDimensions,
        passenger_rate:             float,
        destination_probabilities:  dict,
        vm_request_rate:            float,
        platforms:                  list,
        rng:                        random.Random,
        id_generator:               PassengerIdGenerator,
        recorder,
    ):
```

Y dentro del cuerpo, junto a `self._id_generator = id_generator`, agregar:

```python
        self._recorder                  = recorder
```

- [ ] **Step 2: Modificar `BoardingLane.__init__`**

En `tracks/boarding_lane.py`, de:

```python
    def __init__(self,track_id: int, start_pos: Vector3, end_pos: Vector3):
        """
        Inicialisacion utiliza __init__ de BaseTrack
        """
        super().__init__(track_id, start_pos, end_pos)
        self.passenger_groups: dict[int, deque[Passenger]] = {}
```

a:

```python
    def __init__(self, track_id: int, start_pos: Vector3, end_pos: Vector3, recorder):
        """
        Inicialisacion utiliza __init__ de BaseTrack
        """
        super().__init__(track_id, start_pos, end_pos)
        self.passenger_groups: dict[int, deque[Passenger]] = {}
        self._recorder = recorder
```

- [ ] **Step 3: Modificar `AccelerationTree.__init__`**

En `tracks/acceleration_tree.py`, de:

```python
    def __init__(
            self,
            track_id: int,
            start_pos: Vector3,
            end_pos: Vector3,
            direction: TreeDirection,
            min_vm_separation: float,
            station_id : int | None = None
    ):
        super().__init__(track_id, start_pos, end_pos)
        self.direction = direction
        self.base_acceleration = self._compute_effective_acceleration()
        self.station_id = station_id
```

a:

```python
    def __init__(
            self,
            track_id: int,
            start_pos: Vector3,
            end_pos: Vector3,
            direction: TreeDirection,
            min_vm_separation: float,
            recorder,
            station_id : int | None = None
    ):
        super().__init__(track_id, start_pos, end_pos)
        self.direction = direction
        self.base_acceleration = self._compute_effective_acceleration()
        self.station_id = station_id
        self._recorder = recorder
```

(`recorder` se agrega antes de `station_id` porque `station_id` tiene valor
por defecto y en Python los parámetros sin default no pueden ir después de
uno con default.)

- [ ] **Step 4: Actualizar las construcciones existentes en tests**

En `tests/test_station.py`, `tests/test_boarding_lane.py`,
`tests/test_acceleration_tree.py`: cada llamada a `Station(...)`,
`BoardingLane(...)`, `AccelerationTree(...)` necesita el nuevo argumento
`recorder`. Usar `NullRecorder()`:

```python
from telemetry.recorder import NullRecorder
```

y agregar `recorder=NullRecorder()` (o como argumento posicional en la
posición correcta) a cada construcción existente en esos 3 archivos.

- [ ] **Step 5: Correr los tests existentes y verificar que pasan**

Run: `pytest tests/test_station.py tests/test_boarding_lane.py tests/test_acceleration_tree.py -v`
Expected: PASS (todos los que ya existían, ahora con `recorder` en la firma)

- [ ] **Step 6: Commit**

```bash
git add objects/station.py tracks/boarding_lane.py tracks/acceleration_tree.py \
        tests/test_station.py tests/test_boarding_lane.py tests/test_acceleration_tree.py
git commit -m "feat: inyectar recorder en Station, BoardingLane y AccelerationTree"
```

---

## Task 4: Wiring por constructor — `ContinuousTrain` y `Brain`

**Files:**
- Modify: `systems/continuous_train.py:53-61`
- Modify: `systems/brain.py:57-65`
- Test: `tests/test_continuous_train.py`, `tests/test_brain.py`

**Interfaces:**
- Consume: nada nuevo de fuera
- Produce: `ContinuousTrain` y `Brain` guardan `self._recorder`

- [ ] **Step 1: Modificar `ContinuousTrain.__init__`**

En `systems/continuous_train.py`, de:

```python
    def __init__(
            self,
            start_pos: Vector3,
            end_pos: Vector3,
            density: float,
            vm_factory: Callable,
            rng: random.Random,
            junction_points: dict,
    ):
        self.start_pos  = start_pos
        self.end_pos    = end_pos
```

a:

```python
    def __init__(
            self,
            start_pos: Vector3,
            end_pos: Vector3,
            density: float,
            vm_factory: Callable,
            rng: random.Random,
            junction_points: dict,
            recorder,
    ):
        self.start_pos  = start_pos
        self.end_pos    = end_pos
        self._recorder  = recorder
```

- [ ] **Step 2: Modificar `Brain.__init__`**

En `systems/brain.py`, de:

```python
    def __init__(
        self,
        train: ContinuousTrain,
        network: Network,
        stations: dict,
    ):
        self._train =       train
        self._network =     network
        self._stations =    stations
```

a:

```python
    def __init__(
        self,
        train: ContinuousTrain,
        network: Network,
        stations: dict,
        recorder,
    ):
        self._train =       train
        self._network =     network
        self._stations =    stations
        self._recorder =    recorder
```

- [ ] **Step 3: Actualizar construcciones existentes en tests**

En `tests/test_continuous_train.py` y `tests/test_brain.py`: agregar
`recorder=NullRecorder()` (importar `from telemetry.recorder import
NullRecorder`) a cada construcción de `ContinuousTrain(...)` y `Brain(...)`.

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `pytest tests/test_continuous_train.py tests/test_brain.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add systems/continuous_train.py systems/brain.py \
        tests/test_continuous_train.py tests/test_brain.py
git commit -m "feat: inyectar recorder en ContinuousTrain y Brain"
```

---

## Task 5: Wiring en `station_factory.py` e `inicial.py`

**Files:**
- Modify: `simulation/station_factory.py:73-160` (firma de `create_station`
  y las 3 construcciones internas que hace: `Station`, `BoardingLane` ×N,
  `AccelerationTree` ×2N)
- Modify: `simulation_builder/inicial.py:52-121` (firma de `build` y las
  3 llamadas a `create_station` + construcción de `ContinuousTrain` y `Brain`)
- Test: `tests/test_station_factory.py`

**Interfaces:**
- Consume: `Station`, `BoardingLane`, `AccelerationTree` con el parámetro
  `recorder` agregado en Task 3
- Produce: `create_station(..., recorder) -> tuple[...]`,
  `build(seed, recorder) -> tuple[Brain, dict[int, Station]]`

- [ ] **Step 1: Agregar `recorder` a la firma de `create_station`**

En `simulation/station_factory.py`, la firma pasa de:

```python
def create_station(
    station_id:                 int,                    # ID
    station_origin:             Vector3,                # Cordenadas del centro de la estacion
    num_lanes:                  int,                    # Numero de andenes
    passenger_rate:             float,                  # Tasa de produccion de pasajeros (s)
    destination_probabilities:  dict,                   # diccionario con probabilidades de que pasagero valla a estacion x
    vm_request_rate:            float,                  # Tasa de solicitudes de VMs (s)
    rng:                        random.Random,          # Generador de numeros aleatorios
    id_generator:               PassengerIdGenerator,   # Generador de IDs de pasajeros
    id_alloc:                   TrackIdAllocator,       # Generador de IDs de tracks        
) -> tuple[Station, list, list, list, Junction, Junction]:
```

a (agregar el parámetro al final):

```python
def create_station(
    station_id:                 int,                    # ID
    station_origin:             Vector3,                # Cordenadas del centro de la estacion
    num_lanes:                  int,                    # Numero de andenes
    passenger_rate:             float,                  # Tasa de produccion de pasajeros (s)
    destination_probabilities:  dict,                   # diccionario con probabilidades de que pasagero valla a estacion x
    vm_request_rate:            float,                  # Tasa de solicitudes de VMs (s)
    rng:                        random.Random,          # Generador de numeros aleatorios
    id_generator:               PassengerIdGenerator,   # Generador de IDs de pasajeros
    id_alloc:                   TrackIdAllocator,       # Generador de IDs de tracks
    recorder,                                            # Recorder/NullRecorder de telemetria
) -> tuple[Station, list, list, list, Junction, Junction]:
```

- [ ] **Step 2: Pasar `recorder` a `AccelerationTree` y `BoardingLane` dentro del loop de andenes**

Dentro de `create_station`, en el `for y_i in y_offsets:` (donde se
construyen `up_trees`, `lanes`, `down_trees`), agregar `recorder=recorder`
a las 3 construcciones:

```python
        up_trees.append(AccelerationTree(
            track_id            = up_id,
            start_pos           = j_up_3d,
            end_pos             = extraction,
            direction           = TreeDirection.UP,
            min_vm_separation   = MIN_VM_SEPARATION,
            recorder            = recorder,
            station_id          = None,
        ))
        lanes.append(BoardingLane(
            track_id    = lane_id,
            start_pos   = extraction,
            end_pos     = discharge,
            recorder    = recorder,
        ))
        down_trees.append(AccelerationTree(
            track_id            = down_id,
            start_pos           = discharge,
            end_pos             = j_down_3d,
            direction           = TreeDirection.DOWN,
            min_vm_separation   = MIN_VM_SEPARATION,
            recorder            = recorder,
            station_id          = station_id,
        ))
```

- [ ] **Step 3: Pasar `recorder` a la construcción de `Station`**

Más abajo en `create_station`, donde se construye `Station(...)`, agregar
`recorder=recorder` a los argumentos.

- [ ] **Step 4: Agregar `recorder` a la firma de `build` en `inicial.py`**

En `simulation_builder/inicial.py`, de:

```python
def build(seed: int = 42) -> tuple[Brain, dict[int, Station]]:
    """
    Construye el escenario base.
    Retorna (brain, stations) listo para llamar brain.update(dt, current_time).
    """
    rng     = random.Random(seed)
```

a:

```python
def build(seed: int = 42, recorder=None) -> tuple[Brain, dict[int, Station]]:
    """
    Construye el escenario base.
    Retorna (brain, stations) listo para llamar brain.update(dt, current_time).
    """
    from telemetry.recorder import NullRecorder
    if recorder is None:
        recorder = NullRecorder()
    rng     = random.Random(seed)
```

(default `None` + fallback a `NullRecorder()` para que las ~10 llamadas
existentes a `inicial.build(seed)` en tests, que no pasan `recorder`, sigan
funcionando sin tocarlas.)

- [ ] **Step 5: Pasar `recorder` a las 3 llamadas de `create_station` y a `ContinuousTrain`/`Brain`**

En las 3 llamadas a `create_station(...)` dentro de `build`, agregar
`recorder=recorder,`. En la construcción de `ContinuousTrain(...)`, agregar
`recorder=recorder,`. En `brain = Brain(train=train, network=network,
stations=stations)`, agregar `recorder=recorder`.

- [ ] **Step 6: Correr los tests y verificar que pasan**

Run: `pytest tests/test_station_factory.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add simulation/station_factory.py simulation_builder/inicial.py
git commit -m "feat: propagar recorder a traves de station_factory e inicial.build"
```

---

## Task 6: `main.py` — construir el Recorder, generar `run_id`, y garantizar el cierre

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consume: `Recorder`, `NullRecorder` (Task 1), `TELEMETRY_ENABLED` (Task 2),
  `inicial.build(seed, recorder)` (Task 5)

- [ ] **Step 1: Imports nuevos**

Junto a los demás imports de `main.py`:

```python
from pathlib import Path
from datetime import datetime
from telemetry.recorder import Recorder, NullRecorder
from config.constants import TELEMETRY_ENABLED
```

- [ ] **Step 2: Construir el Recorder antes de `inicial.build`**

Reemplazar:

```python
def main():
    print("Construyendo escenario...")
    brain, stations = inicial.build(seed=42)
```

por:

```python
def main():
    seed = 42
    scenario_name = "inicial"
    run_id = f"{scenario_name}_seed{seed}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir = Path("runs") / run_id
    recorder = Recorder(run_dir, run_id) if TELEMETRY_ENABLED else NullRecorder()

    print(f"Construyendo escenario... (run_id={run_id})")
    brain, stations = inicial.build(seed=seed, recorder=recorder)
```

- [ ] **Step 3: Emitir `run_started` después de construir el escenario**

Justo después de la línea anterior, antes de `sim = Simulation(brain, stations)`:

```python
    recorder.run_started(t=0.0, config={"seed": seed, "scenario_name": scenario_name})
```

- [ ] **Step 4: Envolver el loop principal en try/finally**

El cuerpo de `main()` desde `sim = Simulation(brain, stations)` hasta el
final de la función pasa a estar dentro de un `try/finally`. Reemplazar
desde:

```python
    sim   = Simulation(brain, stations)
    train = brain._train
```

hasta el final del archivo (todo lo que sigue, incluyendo el `while
running:` y el `pygame.quit()` final) por la misma lógica pero indentada
dentro de un `try`, con el cierre en `finally`:

```python
    sim   = Simulation(brain, stations)
    train = brain._train

    try:
        pygame.init()
        pygame.display.set_caption("NSim — Sistema de Transporte Modular")
        screen   = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        clock    = pygame.time.Clock()
        font_sm  = pygame.font.SysFont("dejavusansmono,consolas,couriernew,monospace", 16)
        font_md  = pygame.font.SysFont("dejavusansmono,consolas,couriernew,monospace", 20, bold=True)

        is_fullscreen = False
        windowed_size = (SCREEN_WIDTH, SCREEN_HEIGHT)

        z_belt   = train.start_pos.z
        camera   = Camera(SCREEN_WIDTH, SCREEN_HEIGHT,
                          pos=[1500.0, -600.0, 250.0], yaw=90.0, pitch=-20.0)
        renderer = Renderer(font_sm, font_md)
        inspector = Inspector(font_sm, font_md)

        speed_idx = 0
        paused    = False

        print("Corriendo — Esc para salir (o cerrar fullscreen). F11 = pantalla completa.")
        running = True
        while running:
            dt_real = clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.VIDEORESIZE:
                    if not is_fullscreen:
                        windowed_size = (event.w, event.h)
                        camera.on_resize(event.w, event.h)

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if is_fullscreen:
                            is_fullscreen = False
                            pygame.display.toggle_fullscreen()
                            screen = pygame.display.get_surface()
                            camera.on_resize(*screen.get_size())
                        else:
                            running = False
                    elif event.key == pygame.K_F11:
                        is_fullscreen = not is_fullscreen
                        pygame.display.toggle_fullscreen()
                        screen = pygame.display.get_surface()
                        camera.on_resize(*screen.get_size())

                    elif event.key == pygame.K_SPACE: paused    = not paused
                    elif event.key == pygame.K_1:     speed_idx = 0
                    elif event.key == pygame.K_2:     speed_idx = 1
                    elif event.key == pygame.K_3:     speed_idx = 2
                    elif event.key == pygame.K_4:     speed_idx = 3
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    inspector.handle_click(
                        event.pos, camera, train, brain._network, stations,
                        screen.get_width(),
                    )
                camera.handle_event(event)

            camera.update(dt_real)

            if not paused:
                for _ in range(SPEEDS[speed_idx]):
                    sim.step(DT)

            renderer.render(
                screen, camera, train, brain._network, stations,
                sim.current_time, clock.get_fps(),
                SPEEDS[speed_idx], paused,
            )
            inspector.render(
                screen, camera, train, brain._network, stations,
                screen.get_width(),
            )
            pygame.display.flip()

        pygame.quit()
        print(f"Parado en t={sim.current_time:.1f}s")

    finally:
        summary = {"simulated_seconds": sim.current_time}
        recorder.run_ended(t=sim.current_time, summary=summary)
        recorder.close()

        if TELEMETRY_ENABLED:
            import json
            with open(run_dir / "summary.json", "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            index_path = Path("runs") / "index.jsonl"
            with open(index_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "run_id": run_id, "seed": seed, "scenario_name": scenario_name,
                    "events_path": str(run_dir / "events.jsonl"),
                }) + "\n")
```

(Nota: este Step ya incluye la integración de `Inspector` de la tarea
anterior — si tu `main.py` actual tiene una forma levemente distinta por
ajustes que hiciste, adapta la indentación conservando el `try/finally` y
las 2 líneas de `inspector.handle_click`/`inspector.render`.)

- [ ] **Step 5: Verificación manual**

Run: `python3 main.py`, dejar correr unos segundos, cerrar con Esc.

Expected:
1. Se imprime `Construyendo escenario... (run_id=inicial_seed42_...)`.
2. Al cerrar, existe `runs/<run_id>/events.jsonl` con al menos 2 líneas
   (`run_started` y `run_ended`).
3. Existe `runs/<run_id>/summary.json` con `simulated_seconds`.
4. `runs/index.jsonl` tiene una línea nueva agregada (o creada si es la
   primera corrida).

Luego, para probar la garantía ante crash: agregar temporalmente
`raise RuntimeError("prueba")` justo después de `sim.step(DT)` dentro del
loop, correr, dejar que crashee, y confirmar que **igual** se escribió
`events.jsonl` con su `run_ended` y `summary.json` — después quitar esa
línea de prueba.

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat: integrar Recorder en main.py con cierre garantizado ante crash"
```

---

## Self-Review

**Spec coverage:**
- Paquete `telemetry/` sin dependencias del proyecto → Task 1.
- Formato de evento base (`schema_version`, `seq`, `t`, `type`) → Task 1.
- Buffer + flush cada N + flush en `close()` → Task 1.
- Serialización de Enums → Task 1 (`_json_default`).
- `NullRecorder` → Task 1.
- `TELEMETRY_ENABLED` → Task 2.
- Wiring por constructor en las 6 clases/funciones listadas en la spec →
  Tasks 3, 4, 5.
- `run_id`, layout `runs/<run_id>/events.jsonl` + `summary.json` +
  `runs/index.jsonl` → Task 6.
- Garantía de flush ante crash (`try/finally`) → Task 6.

**Placeholder scan:** sin TBD/TODO — todo el código de cada step está completo.

**Type consistency:** `Recorder.run_started(t, config)` / `run_ended(t,
summary)` se usan con la misma firma en Task 1 y Task 6. El parámetro
`recorder` se llama igual (`recorder`) en las 6 clases/funciones de Tasks
3-5, sin variar el nombre entre ellas.