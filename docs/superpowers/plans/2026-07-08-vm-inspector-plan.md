# VM Inspector Implementation Plan

> **Nota de flujo:** Daniel escribe el código él mismo — el asistente entrega
> el contenido de cada archivo como texto, nunca usa Edit/Write sobre archivos
> del proyecto. Este documento sirve como referencia de qué se construyó y
> por qué, no como instrucciones para un subagente que edite archivos.

**Goal:** Permitir hacer click en un VM o estación durante la simulación y
abrir un panel resumen que se actualiza en vivo, con resaltado del objeto
seleccionado y línea conectora hacia su panel.

**Architecture:** Módulo nuevo `simulation/inspector.py` con la clase
`Inspector`. Encapsula picking (proyección + radio + profundidad),
resolución de ubicación de un VM cada frame (belt / árbol / boarding lane),
contenido textual por plantilla, layout en grilla de burbujas, y el dibujo
de resaltado + línea conectora. `renderer.py` no se modifica. `main.py` solo
instancia `Inspector`, enruta el click izquierdo y llama a `render()`.

**Tech Stack:** Python 3, pygame (ya en uso en el proyecto).

## Global Constraints

- No modificar `renderer.py`, `camera.py`, `brain.py`, ni archivos de
  `objects/`/`tracks/`/`systems/`.
- Seguir el spec: `docs/superpowers/specs/2026-07-08-vm-inspector-design.md`.
- Sin test automatizado para el ciclo pygame completo (igual que el resto de
  `simulation/`, según `CLAUDE.md`) — sí se testean las funciones puras de
  layout y contenido, que no dependen de pygame para su lógica.

---

## Task 1: Funciones puras de layout y contenido

**Files:**
- Create: `simulation/inspector.py` (solo las funciones de módulo, sin la
  clase `Inspector` todavía)
- Test: `tests/test_inspector.py`

**Interfaces:**
- Produce: `panel_position(index: int, screen_width: int) -> tuple[int, int]`
- Produce: `closest_anchor(x: int, y: int, target: tuple[int, int]) -> tuple[int, int]`
- Produce: constantes `PANEL_W, PANEL_H, GAP, MARGIN, PICK_RADIUS_VM, PICK_RADIUS_STATION`

- [ ] **Step 1: Escribir tests de `panel_position`**

```python
# tests/test_inspector.py
from simulation.inspector import panel_position, closest_anchor, PANEL_W, PANEL_H, GAP, MARGIN

def test_panel_position_first_bubble_top_left():
    assert panel_position(0, 1920) == (MARGIN, MARGIN)

def test_panel_position_second_bubble_moves_right():
    x0, y0 = panel_position(0, 1920)
    x1, y1 = panel_position(1, 1920)
    assert y1 == y0
    assert x1 == x0 + PANEL_W + GAP

def test_panel_position_wraps_to_next_row():
    # con screen_width chico, solo entra 1 columna
    narrow = MARGIN + PANEL_W + 1
    x0, y0 = panel_position(0, narrow)
    x1, y1 = panel_position(1, narrow)
    assert x1 == x0
    assert y1 == y0 + PANEL_H + GAP
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `pytest tests/test_inspector.py -v`
Expected: FAIL con `ModuleNotFoundError` o `ImportError` (el módulo no existe aún)

- [ ] **Step 3: Crear `simulation/inspector.py` con las funciones puras**

```python
"""
inspector.py — Click-to-inspect: paneles de resumen en vivo para VMs y
estaciones.

Responsabilidades:
    - Detectar click sobre un VM (belt/árbol/boarding lane) o una estación
    - Mantener la lista de paneles abiertos, releyendo su contenido cada frame
    - Dibujar las burbujas de resumen, el resaltado del objeto seleccionado
      y la línea conectora hacia su panel

Lo que NO hace:
    - No mueve nada ni cambia el estado de la simulación
    - No maneja mouse look de cámara — main.py decide cuándo llamar
"""
import pygame
from config.constants import VM_RENDER_WIDTH, VM_RENDER_DEPTH, VM_RENDER_HEIGHT
from tracks.acceleration_tree import AccelerationTree
from tracks.boarding_lane import BoardingLane
from simulation.renderer import BOX_EDGES

# ─── LAYOUT ────────────────────────────────────────────────────────────────

PANEL_W = 220
PANEL_H = 190
GAP     = 8
MARGIN  = 8

PICK_RADIUS_VM      = 14
PICK_RADIUS_STATION = 30

PANEL_BG     = (  8,  12,  20, 220)
PANEL_BORDER = ( 30, 120, 255)
ACCENT       = ( 30, 120, 255)
TEXT_BRIGHT  = (220, 230, 245)
TEXT_DIM     = ( 90, 105, 125)
CLOSE_COLOR  = (255,  90,  90)

CLOSE_BOX_SIZE = 18
CLOSE_BOX_MARGIN = 4


def panel_position(index: int, screen_width: int) -> tuple[int, int]:
    """
    Posición (x, y) en píxeles de la burbuja en el índice dado, en una
    grilla que llena filas de izquierda a derecha y baja al llegar al
    borde de la pantalla.
    """
    cols = max(1, (screen_width - MARGIN) // (PANEL_W + GAP))
    row = index // cols
    col = index % cols
    x = MARGIN + col * (PANEL_W + GAP)
    y = MARGIN + row * (PANEL_H + GAP)
    return x, y


def closest_anchor(x: int, y: int, target: tuple[int, int]) -> tuple[int, int]:
    """
    Punto sobre el borde del panel [x, y, x+PANEL_W, y+PANEL_H] más cercano
    a `target` — de ahí sale la línea conectora hacia el objeto 3D.
    """
    tx, ty = target
    left, right = x, x + PANEL_W
    top, bottom = y, y + PANEL_H

    if left <= tx <= right and top <= ty <= bottom:
        candidates = [
            (tx - left,   (left,  ty)),
            (right - tx,  (right, ty)),
            (ty - top,    (tx,    top)),
            (bottom - ty, (tx,    bottom)),
        ]
        return min(candidates, key=lambda c: c[0])[1]

    cx = min(max(tx, left), right)
    cy = min(max(ty, top), bottom)
    return cx, cy


def _dist(a: tuple[int, int], b: tuple[int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `pytest tests/test_inspector.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add simulation/inspector.py tests/test_inspector.py
git commit -m "feat: layout puro de burbujas del inspector"
```

---

## Task 2: Resolución de ubicación de un VM y contenido de panel

**Files:**
- Modify: `simulation/inspector.py` (agregar funciones de resolución/contenido)
- Test: `tests/test_inspector.py` (agregar tests con dobles de prueba simples)

**Interfaces:**
- Consume: `AccelerationTree`, `BoardingLane` (de `tracks/`), objetos
  `ModularVehicle`/`Station` reales del dominio (ver spec para atributos usados)
- Produce: `resolve_vm_location(vm, train, network, stations) -> dict | None`
- Produce: `resolve_station_location(station_id, stations) -> dict | None`
- Produce: `panel_content(panel: dict, loc: dict) -> tuple[str, list[str]]`

- [ ] **Step 1: Escribir tests con dobles de prueba (fakes) simples**

```python
# agregar a tests/test_inspector.py
from simulation.inspector import resolve_vm_location, panel_content

class FakeVM:
    def __init__(self, vehicle_id, slot_index=None):
        self.vehicle_id = vehicle_id
        self.slot_index = slot_index
        self.capacity = 6
        self.passengers_on_board = []
        self.destination_station_id = None
        from objects.types import ModularVehicleState
        self.state = ModularVehicleState.MOVING

    @property
    def passenger_count(self):
        return len(self.passengers_on_board)

    @property
    def has_destination(self):
        return self.destination_station_id is not None


class FakeTrain:
    def __init__(self, slots):
        self.slots = slots
        from objects.math3d import Vector3
        self.start_pos = Vector3(0, 0, 0)

    def get_slot_belt_x(self, i):
        return float(i)


class FakeNetwork:
    def __init__(self):
        self.tracks = {}


def _empty_slot():
    return {
        'vm': None, 'colliding_vms': [],
        'reserved_station_id': None, 'destination_station_id': None,
        'demand_station_id': None,
    }


def test_resolve_vm_location_on_belt():
    vm = FakeVM(vehicle_id=1, slot_index=2)
    slots = [_empty_slot(), _empty_slot(), _empty_slot()]
    slots[2]['vm'] = vm
    train = FakeTrain(slots)

    loc = resolve_vm_location(vm, train, FakeNetwork(), {})

    assert loc is not None
    assert loc['template'] == 'belt'
    assert loc['slot_index'] == 2


def test_resolve_vm_location_missing_returns_none():
    vm = FakeVM(vehicle_id=1, slot_index=None)
    train = FakeTrain([_empty_slot()])

    loc = resolve_vm_location(vm, train, FakeNetwork(), {})

    assert loc is None


def test_panel_content_belt_lists_active_labels():
    vm = FakeVM(vehicle_id=42, slot_index=0)
    slot = _empty_slot()
    slot['vm'] = vm
    slot['destination_station_id'] = 2
    loc = {'template': 'belt', 'slot': slot, 'slot_index': 0}
    panel = {'kind': 'vm', 'ref': vm}

    title, lines = panel_content(panel, loc)

    assert title == "VM #42"
    assert any("DEST" in line and "S2" in line for line in lines)
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `pytest tests/test_inspector.py -v`
Expected: FAIL con `ImportError: cannot import name 'resolve_vm_location'`

- [ ] **Step 3: Implementar resolución y contenido en `simulation/inspector.py`**

Agregar al final del archivo (después de `_dist`):

```python
# ─── RESOLUCIÓN DE UBICACIÓN ─────────────────────────────────────────────

def _owning_station_id(track, stations) -> int | None:
    """
    Ni AccelerationTree(UP) ni BoardingLane guardan su station_id (solo el
    árbol DOWN lo tiene) — se busca recorriendo las plataformas de cada
    estación, igual que renderer.py accede a atributos internos de Station
    para dibujar (ej. _walking).
    """
    for station in stations.values():
        for platform in station._platforms:
            if platform['up_tree_id'] == track.track_id:
                return station.station_id
            if platform['down_tree_id'] == track.track_id:
                return station.station_id
            if platform['lane'] is track:
                return station.station_id
    return None


def resolve_vm_location(vm, train, network, stations) -> dict | None:
    """
    Encuentra dónde está el VM AHORA (belt, árbol o boarding lane) y
    retorna un dict con su posición 3D y el contexto necesario para
    describirlo. Retorna None si el VM no está en ningún lado — señal para
    que Inspector cierre el panel automáticamente.
    """
    if vm.slot_index is not None:
        slot = train.slots[vm.slot_index]
        if slot['vm'] is vm:
            return {
                'template':   'belt',
                'slot':       slot,
                'slot_index': vm.slot_index,
                'pos':        (train.get_slot_belt_x(vm.slot_index),
                               train.start_pos.y, train.start_pos.z),
            }

    for track in network.tracks.values():
        data = track.vehicles.get(vm.vehicle_id)
        if data is None or data['vehicle'] is not vm:
            continue
        progress = data['distance'] / track.length if track.length > 0 else 0.0
        p = track.position_at_progress(progress)
        station_id = _owning_station_id(track, stations)

        if isinstance(track, AccelerationTree):
            return {
                'template':   'tree', 'track': track, 'data': data,
                'progress':   progress, 'station_id': station_id,
                'pos':        (p.x, p.y, p.z),
            }
        if isinstance(track, BoardingLane):
            return {
                'template':   'lane', 'track': track, 'data': data,
                'progress':   progress, 'station_id': station_id,
                'pos':        (p.x, p.y, p.z),
            }
    return None


def resolve_station_location(station_id: int, stations: dict) -> dict | None:
    """Retorna la posición 3D del centro de la estación, o None si ya no existe."""
    station = stations.get(station_id)
    if station is None:
        return None
    ht = station.dimensions.floor_height
    return {
        'template': 'station',
        'station':  station,
        'pos':      (station.origin.x, station.origin.y, station.origin.z + ht / 2),
    }


# ─── CONTENIDO DE PANEL ───────────────────────────────────────────────────

def _slot_labels(slot: dict) -> list[str]:
    labels = []
    if slot.get('reserved_station_id') is not None:
        labels.append(f"RESERVED→S{slot['reserved_station_id']}")
    if slot.get('destination_station_id') is not None:
        labels.append(f"DEST→S{slot['destination_station_id']}")
    if slot.get('demand_station_id') is not None:
        labels.append(f"DEMAND→S{slot['demand_station_id']}")
    return labels


def panel_content(panel: dict, loc: dict) -> tuple[str, list[str]]:
    """
    Retorna (titulo, lineas) para dibujar un panel. Sin dependencias de
    pygame — la plantilla se elige según loc['template'], recalculada cada
    frame por Inspector, así que si el VM cambia de ubicación el contenido
    cambia solo, sin reabrir el panel.
    """
    if panel['kind'] == 'station':
        station = loc['station']
        summary = station.get_summary()
        lines = [
            f"Andenes: {summary['active_platforms']}/{summary['platforms']} activos",
            f"Demanda pendiente: {station.pending_demand}",
            f"Caminando hacia anden: {len(station._walking)}",
            f"Tasa pasajeros: {summary['passenger_rate']:.2f}/s",
            f"Tasa VMs: {summary['vm_request_rate']:.2f}/s",
            f"Destinos: {summary['destinations']}",
        ]
        return f"Estacion S{summary['station_id']}", lines

    vm = panel['ref']
    template = loc['template']
    lines = []

    if template == 'tree':
        track = loc['track']
        lines.append(f"Ubicacion: Arbol {track.direction.value} #{track.track_id} "
                     f"(S{loc['station_id']})")
        lines.append(f"Progreso: {loc['progress'] * 100:.0f}%")
    elif template == 'lane':
        track = loc['track']
        lines.append(f"Ubicacion: BoardingLane #{track.track_id} (S{loc['station_id']})")
        lines.append(f"Progreso: {loc['progress'] * 100:.0f}%")

    lines.append(f"Estado: {vm.state.value}")
    lines.append(f"Cap: {vm.passenger_count}/{vm.capacity} pasajeros")
    lines.append(f"Destino: S{vm.destination_station_id}" if vm.has_destination
                 else "Destino: (sin asignar)")

    if template == 'belt':
        slot = loc['slot']
        lines.append(f"Slot: {loc['slot_index']}")
        labels = _slot_labels(slot)
        if slot['colliding_vms']:
            labels.append(f"CHOQUE! ({len(slot['colliding_vms']) + 1} VMs)")
        lines.append(f"Etiquetas: {', '.join(labels) if labels else '(ninguna)'}")

    if template == 'lane':
        data = loc['data']
        if data['boarding_committed']:
            lines.append("Embarcando: no")
        else:
            lines.append(f"Embarcando: si ({len(data['passengers'])} subiendo)")
        lines.append("Pasajeros a bordo:")
        for p in vm.passengers_on_board:
            lines.append(f"  S{p.origin_station_id}-{p.passenger_id} -> S{p.destination_station_id}")

    return f"VM #{vm.vehicle_id}", lines
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `pytest tests/test_inspector.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add simulation/inspector.py tests/test_inspector.py
git commit -m "feat: resolucion de ubicacion y contenido de panel del inspector"
```

---

## Task 3: Clase `Inspector` — picking, estado de paneles, render

**Files:**
- Modify: `simulation/inspector.py` (agregar la clase `Inspector`)
- No requiere tests nuevos automatizados (picking y dibujo dependen de
  pygame real — se verifica corriendo `main.py`, igual que el resto de
  `simulation/`)

**Interfaces:**
- Consume: `panel_position`, `closest_anchor`, `resolve_vm_location`,
  `resolve_station_location`, `panel_content` (Task 1 y 2)
- Produce: `class Inspector` con `__init__(self, font_sm, font_md)`,
  `handle_click(self, pos, camera, train, network, stations, screen_width)`,
  `render(self, surface, camera, train, network, stations, screen_width)`

- [ ] **Step 1: Implementar la clase al final de `simulation/inspector.py`**

```python
# ─── INSPECTOR ─────────────────────────────────────────────────────────────

class Inspector:
    """
    Detecta clicks sobre VMs/estaciones, mantiene los paneles abiertos y los
    dibuja junto con el resaltado del objeto seleccionado.

    No almacena copias de estado — cada panel guarda solo una referencia
    ({'kind': 'vm', 'ref': vm} o {'kind': 'station', 'station_id': N}) y el
    contenido se relee cada frame desde el objeto real.

    Uso:
        inspector = Inspector(font_sm, font_md)
        inspector.handle_click(mouse_pos, camera, train, network, stations, W)
        inspector.render(surface, camera, train, network, stations, W)
    """

    def __init__(self, font_sm: pygame.font.Font, font_md: pygame.font.Font):
        self._font_sm = font_sm
        self._font_md = font_md
        self._panels: list[dict] = []

    # ── API pública ─────────────────────────────────────────────────────

    def handle_click(self, pos, camera, train, network, stations, screen_width) -> None:
        if self._try_close(pos, screen_width):
            return
        target = self._pick(pos, camera, train, network, stations)
        if target is None or self._is_already_open(target):
            return
        self._panels.append(target)

    def render(self, surface, camera, train, network, stations, screen_width) -> None:
        resolved = []
        for panel in self._panels:
            loc = self._resolve(panel, train, network, stations)
            if loc is not None:
                resolved.append((panel, loc))
        self._panels = [p for p, _ in resolved]  # auto-cierre de paneles huérfanos

        for i, (panel, loc) in enumerate(resolved):
            x, y = panel_position(i, screen_width)
            self._draw_highlight_and_line(surface, camera, x, y, panel, loc)
            self._draw_panel(surface, x, y, panel, loc)

    # ── Picking ──────────────────────────────────────────────────────────

    def _try_close(self, pos, screen_width) -> bool:
        for i in range(len(self._panels)):
            x, y = panel_position(i, screen_width)
            close_rect = pygame.Rect(
                x + PANEL_W - CLOSE_BOX_SIZE - CLOSE_BOX_MARGIN, y + CLOSE_BOX_MARGIN,
                CLOSE_BOX_SIZE, CLOSE_BOX_SIZE,
            )
            if close_rect.collidepoint(pos):
                del self._panels[i]
                return True
        return False

    def _pick(self, pos, camera, train, network, stations) -> dict | None:
        candidates = []  # list[(depth, target)]

        for i, slot in enumerate(train.slots):
            vm = slot['vm']
            if vm is None:
                continue
            bx = train.get_slot_belt_x(i)
            proj = camera.project(bx, train.start_pos.y, train.start_pos.z)
            if proj is None:
                continue
            sx, sy, depth = proj
            if _dist(pos, (sx, sy)) <= PICK_RADIUS_VM:
                candidates.append((depth, {'kind': 'vm', 'ref': vm}))

        for track in network.tracks.values():
            for data in track.vehicles.values():
                vm = data['vehicle']
                progress = data['distance'] / track.length if track.length > 0 else 0.0
                p = track.position_at_progress(progress)
                proj = camera.project(p.x, p.y, p.z)
                if proj is None:
                    continue
                sx, sy, depth = proj
                if _dist(pos, (sx, sy)) <= PICK_RADIUS_VM:
                    candidates.append((depth, {'kind': 'vm', 'ref': vm}))

        for station in stations.values():
            ht = station.dimensions.floor_height
            proj = camera.project(station.origin.x, station.origin.y, station.origin.z + ht / 2)
            if proj is None:
                continue
            sx, sy, depth = proj
            if _dist(pos, (sx, sy)) <= PICK_RADIUS_STATION:
                candidates.append((depth, {'kind': 'station', 'station_id': station.station_id}))

        if not candidates:
            return None
        candidates.sort(key=lambda c: c[0])
        return candidates[0][1]

    def _is_already_open(self, target: dict) -> bool:
        for panel in self._panels:
            if panel['kind'] != target['kind']:
                continue
            if target['kind'] == 'vm' and panel['ref'] is target['ref']:
                return True
            if target['kind'] == 'station' and panel['station_id'] == target['station_id']:
                return True
        return False

    def _resolve(self, panel, train, network, stations) -> dict | None:
        if panel['kind'] == 'vm':
            return resolve_vm_location(panel['ref'], train, network, stations)
        return resolve_station_location(panel['station_id'], stations)

    # ── Dibujo ───────────────────────────────────────────────────────────

    def _draw_highlight_and_line(self, surface, camera, x, y, panel, loc) -> None:
        px, py, pz = loc['pos']
        proj = camera.project(px, py, pz)
        if proj is None:
            return
        sx, sy, _ = proj

        if panel['kind'] == 'station':
            self._draw_station_highlight(surface, camera, loc['station'])
        else:
            self._draw_vm_highlight(surface, camera, px, py, pz)

        anchor = closest_anchor(x, y, (sx, sy))
        pygame.draw.line(surface, ACCENT, anchor, (sx, sy), 1)

    def _draw_vm_highlight(self, surface, camera, cx, cy, cz) -> None:
        hw, hd, ht = VM_RENDER_WIDTH / 2, VM_RENDER_DEPTH / 2, VM_RENDER_HEIGHT
        verts = [
            (cx - hw, cy - hd, cz),      (cx + hw, cy - hd, cz),
            (cx + hw, cy + hd, cz),      (cx - hw, cy + hd, cz),
            (cx - hw, cy - hd, cz + ht), (cx + hw, cy - hd, cz + ht),
            (cx + hw, cy + hd, cz + ht), (cx - hw, cy + hd, cz + ht),
        ]
        self._draw_wireframe(surface, camera, verts)

    def _draw_station_highlight(self, surface, camera, station) -> None:
        ox, oy, oz = station.origin.x, station.origin.y, station.origin.z
        hw = station.dimensions.x_length / 2.0
        hl = station.dimensions.y_length / 2.0
        ht = station.dimensions.floor_height
        verts = [
            (ox - hw, oy - hl, oz),      (ox + hw, oy - hl, oz),
            (ox + hw, oy + hl, oz),      (ox - hw, oy + hl, oz),
            (ox - hw, oy - hl, oz + ht), (ox + hw, oy - hl, oz + ht),
            (ox + hw, oy + hl, oz + ht), (ox - hw, oy + hl, oz + ht),
        ]
        self._draw_wireframe(surface, camera, verts)

    @staticmethod
    def _draw_wireframe(surface, camera, verts) -> None:
        for a, b in BOX_EDGES:
            seg = camera.project_segment(*verts[a], *verts[b])
            if seg:
                pygame.draw.line(surface, ACCENT, seg[0], seg[1], 3)

    def _draw_panel(self, surface, x, y, panel, loc) -> None:
        title, lines = panel_content(panel, loc)

        panel_surf = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)
        panel_surf.fill(PANEL_BG)
        pygame.draw.rect(panel_surf, PANEL_BORDER, panel_surf.get_rect(), 1)

        title_surf = self._font_md.render(title, True, TEXT_BRIGHT)
        panel_surf.blit(title_surf, (8, 6))

        for i, line in enumerate(lines):
            y_off = 30 + i * 15
            if y_off > PANEL_H - 12:
                break
            line_surf = self._font_sm.render(line[:34], True, TEXT_DIM)
            panel_surf.blit(line_surf, (8, y_off))

        cx0 = PANEL_W - CLOSE_BOX_SIZE - CLOSE_BOX_MARGIN
        cy0 = CLOSE_BOX_MARGIN
        pygame.draw.line(panel_surf, CLOSE_COLOR, (cx0, cy0), (cx0 + CLOSE_BOX_SIZE, cy0 + CLOSE_BOX_SIZE), 2)
        pygame.draw.line(panel_surf, CLOSE_COLOR, (cx0 + CLOSE_BOX_SIZE, cy0), (cx0, cy0 + CLOSE_BOX_SIZE), 2)

        surface.blit(panel_surf, (x, y))
```

- [ ] **Step 2: Verificación manual (sin test automatizado — igual criterio que `renderer.py`/`camera.py`)**

Se verifica en la Task 4, corriendo `main.py`, ya que requiere el loop
completo de eventos y una ventana pygame real.

- [ ] **Step 3: Commit**

```bash
git add simulation/inspector.py
git commit -m "feat: clase Inspector con picking, render de paneles y resaltado"
```

---

## Task 4: Integración en `main.py`

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consume: `Inspector` (Task 3), API pública tal como quedó definida ahí

- [ ] **Step 1: Import y creación de la instancia**

En `main.py`, junto a los demás imports de `simulation`:

```python
from simulation.inspector import Inspector
```

Después de crear `renderer` (línea `renderer = Renderer(font_sm, font_md)`):

```python
    inspector = Inspector(font_sm, font_md)
```

- [ ] **Step 2: Enrutar el click izquierdo**

Dentro del `for event in pygame.event.get():`, junto a los demás
`elif event.type == ...`, agregar (antes de `camera.handle_event(event)`
para no interferir con mouse look, que solo reacciona a botón derecho):

```python
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                inspector.handle_click(
                    event.pos, camera, train, brain._network, stations,
                    screen.get_width(),
                )
```

- [ ] **Step 3: Dibujar el inspector después del render principal**

Después de la llamada a `renderer.render(...)` y antes de
`pygame.display.flip()`:

```python
        inspector.render(
            screen, camera, train, brain._network, stations,
            screen.get_width(),
        )
```

- [ ] **Step 4: Verificación manual**

Run: `python3 main.py`
Pasos a probar:
1. Click en un VM visible en el belt (cámara cerca, LOD de caja) → aparece
   panel arriba a la izquierda con slot/etiquetas, línea conectora visible,
   caja del VM con borde más grueso.
2. Click en un segundo VM → aparece una segunda burbuja a la derecha de la
   primera.
3. Abrir suficientes paneles para llenar el ancho de pantalla → el siguiente
   baja a una segunda fila.
4. Click en la X de un panel → se cierra y los siguientes se recorren para
   no dejar hueco.
5. Click en un VM que ya tiene panel abierto → no pasa nada (no se duplica).
6. Click en una estación → aparece panel con demanda pendiente, andenes
   activos, etc.
7. Esperar a que un VM con panel abierto cruce de belt → árbol → boarding
   lane → confirmar que el contenido del panel cambia de plantilla solo,
   sin recliquear.

Expected: los 7 pasos se comportan como se describe, sin excepciones en
consola.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: integrar Inspector en el loop principal de main.py"
```

---

## Self-Review

**Spec coverage:**
- Picking por radio + profundidad → Task 3, `_pick`.
- Auto-cierre si el VM/estación desaparece → Task 3, `render` (filtra por
  `resolve_*` retornando `None`).
- No duplicar panel del mismo objeto → Task 3, `_is_already_open`.
- Contenido dinámico según ubicación (belt/tree/lane) → Task 2,
  `resolve_vm_location` + `panel_content`.
- Layout en grilla con altura fija → Task 1, `panel_position`.
- Resaltado con borde más grueso → Task 3, `_draw_vm_highlight` /
  `_draw_station_highlight`.
- Línea conectora desde el borde más cercano → Task 1, `closest_anchor`;
  Task 3, `_draw_highlight_and_line`.
- `renderer.py` sin cambios → confirmado, solo se importa `BOX_EDGES`.

**Placeholder scan:** sin TBD/TODO, todo el código de cada step está completo.

**Type consistency:** `panel_position`, `closest_anchor`, `resolve_vm_location`,
`resolve_station_location`, `panel_content` se usan con la misma firma en
Task 1/2 y en la clase `Inspector` de Task 3.
