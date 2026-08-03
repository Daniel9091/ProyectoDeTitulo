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
from config.constants import VM_RENDER_WIDTH, VM_RENDER_DEPTH, VM_RENDER_HEIGHT, TRAIN_SPEED, BOARDING_LANE_SPEED
from tracks.acceleration_tree import AccelerationTree
from tracks.boarding_lane import BoardingLane
from simulation.renderer import BOX_EDGES
import simulation.palette as palette


# ─── LAYOUT ────────────────────────────────────────────────────────────────

PANEL_W        = 300
PANEL_H        = 300
GAP            = 8
MARGIN         = 8
HEADER_H       = 42
SECTION_LABEL_H = 16
ROW_H          = 18
SECTION_PAD    = 6

PICK_RADIUS_VM      = 14
PICK_RADIUS_STATION = 30

PANEL_BG     = (  8,  12,  20, 220)
PANEL_BORDER = ( 30, 120, 255)
ACCENT       = ( 30, 120, 255)
TEXT_BRIGHT  = (220, 230, 245)
TEXT_DIM     = (165, 180, 200)
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

def _find_belt_slot(vm, train):
    """
    Busca al VM por identidad en train.slots — el dominio nunca mantiene
    vm.slot_index actualizado (ver systems/continuous_train.py: place_vm y
    remove_vm no lo tocan), así que se escanea por igualdad de objeto,
    igual que ya hace _pick(). También busca dentro de colliding_vms para
    poder inspeccionar cualquier VM de un choque, no solo el titular.

    Retorna (slot_index, slot, stack_offset) o None.
    stack_offset es 0 para el VM titular del slot, o su posición (>=1)
    dentro de slot['colliding_vms'] si está apilado por un choque.
    """
    for i, slot in enumerate(train.slots):
        if slot['vm'] is vm:
            return i, slot, 0
        for stack_i, other in enumerate(slot['colliding_vms']):
            if other is vm:
                return i, slot, stack_i + 1
    return None

def resolve_vm_location(vm, train, network, stations) -> dict | None:
    """
    Encuentra dónde está el VM AHORA (belt, árbol o boarding lane) y
    retorna un dict con su posición 3D y el contexto necesario para
    describirlo. Retorna None si el VM no está en ningún lado — señal para
    que Inspector cierre el panel automáticamente.
    """
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

    found = _find_belt_slot(vm, train)
    if found is not None:
        slot_index, slot, stack_offset = found
        z = train.start_pos.z + stack_offset * VM_RENDER_HEIGHT
        return {
            'template':     'belt',
            'slot':         slot,
            'slot_index':   slot_index,
            'stack_offset': stack_offset,
            'pos':          (train.get_slot_belt_x(slot_index), train.start_pos.y, z),
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
        total_in_slot = 1 + len(slot['colliding_vms'])
        if slot['colliding_vms']:
            labels.append(f"CHOQUE! ({total_in_slot} VMs)")
            lines.append(f"Posicion en choque: {loc['stack_offset'] + 1}/{total_in_slot}")
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
        self._font_xs = pygame.font.SysFont(
            "dejavusansmono,consolas,couriernew,monospace", 13
        )
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
            bx = train.get_slot_belt_x(i)
            if slot['vm'] is not None:
                proj = camera.project(bx, train.start_pos.y, train.start_pos.z)
                if proj is not None:
                    sx, sy, depth = proj
                    if _dist(pos, (sx, sy)) <= PICK_RADIUS_VM:
                        candidates.append((depth, {'kind': 'vm', 'ref': slot['vm']}))
            for stack_i, other in enumerate(slot['colliding_vms']):
                z = train.start_pos.z + (stack_i + 1) * VM_RENDER_HEIGHT
                proj = camera.project(bx, train.start_pos.y, z)
                if proj is not None:
                    sx, sy, depth = proj
                    if _dist(pos, (sx, sy)) <= PICK_RADIUS_VM:
                        candidates.append((depth, {'kind': 'vm', 'ref': other}))

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
        title, subtitle = self._get_title_subtitle(panel, loc)

        panel_surf = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)
        panel_surf.fill(palette.active["panel_bg"])
        pygame.draw.rect(panel_surf, PANEL_BORDER, panel_surf.get_rect(), 1)

        self._draw_header(panel_surf, title, subtitle)

        if panel['kind'] == 'vm':
            self._draw_vm_panel(panel_surf, panel['ref'], loc)
        else:
            self._draw_station_panel(panel_surf, loc['station'])

        cx0 = PANEL_W - CLOSE_BOX_SIZE - CLOSE_BOX_MARGIN
        cy0 = CLOSE_BOX_MARGIN
        pygame.draw.line(panel_surf, CLOSE_COLOR,
                         (cx0, cy0), (cx0 + CLOSE_BOX_SIZE, cy0 + CLOSE_BOX_SIZE), 2)
        pygame.draw.line(panel_surf, CLOSE_COLOR,
                         (cx0 + CLOSE_BOX_SIZE, cy0), (cx0, cy0 + CLOSE_BOX_SIZE), 2)

        surface.blit(panel_surf, (x, y))

    # ── Encabezado ───────────────────────────────────────────────────────

    def _draw_header(self, surf, title, subtitle) -> None:
        # Línea de acento delgada arriba — sin fondo sólido
        pygame.draw.rect(surf, ACCENT, (0, 0, PANEL_W, 3))

        title_surf = self._font_md.render(title, True, palette.active["text_bright"])
        if title_surf.get_width() > PANEL_W - 44:
            title_surf = self._font_sm.render(title, True, palette.active["text_bright"])
        surf.blit(title_surf, (8, 6))

        sub_surf = self._font_sm.render(subtitle, True, palette.active["text_dim"])
        surf.blit(sub_surf, (8, 25))

        pygame.draw.line(surf, PANEL_BORDER, (0, HEADER_H), (PANEL_W, HEADER_H), 1)

    # ── Panel VM ─────────────────────────────────────────────────────────

    def _draw_vm_panel(self, surf, vm, loc) -> None:
        y = HEADER_H + 2

        y = self._draw_section_label(surf, "ESTADO", y)
        surf.blit(
            self._font_sm.render(self._friendly_state(vm, loc),
                                 True, palette.active["text_bright"]),
            (12, y)
        )
        vel_surf = self._font_sm.render(
            f"{self._vm_velocity(loc):.1f} m/s", True, palette.active["text_dim"]
        )
        surf.blit(vel_surf, (PANEL_W - vel_surf.get_width() - 10, y))
        y += ROW_H
        self._draw_bar(surf, 26, y + 2, 90, 9,
                       vm.passenger_count / max(vm.capacity, 1))
        surf.blit(
            self._font_sm.render(f"{vm.passenger_count}/{vm.capacity}",
                                 True, palette.active["text_dim"]),
            (124, y)
        )
        y += ROW_H

        # ── ABORDANDO (solo si está en boarding lane) ────────────────────
        if loc['template'] == 'lane':
            data = loc['data']
            if not data.get('boarding_committed', True):
                boarding = data.get('passengers', [])
                note = f"+ {len(boarding)} subiendo" if boarding else "Sin pasajeros en cola"
                surf.blit(
                    self._font_sm.render(note, True, palette.active["text_dim"]),
                    (12, y)
                )
                y += ROW_H

        labels = self._vm_label_lines(loc)
        if labels:
            y = self._draw_separator(surf, y)
            y = self._draw_section_label(surf, "ETIQUETAS", y)
            for lbl in labels:
                if y + ROW_H > PANEL_H - 8:
                    break
                surf.blit(
                    self._font_sm.render(lbl, True, palette.active["text_bright"]),
                    (12, y)
                )
                y += ROW_H

        if vm.passenger_count > 0:
            y = self._draw_separator(surf, y)
            y = self._draw_section_label(surf, "PASAJEROS A BORDO", y)
            for p in vm.passengers_on_board:
                if y + ROW_H > PANEL_H - 8:
                    surf.blit(
                        self._font_sm.render("...", True, palette.active["text_dim"]),
                        (12, y)
                    )
                    break
                line = f"#{p.passenger_id:03d}  S{p.origin_station_id}→S{p.destination_station_id}"
                surf.blit(
                    self._font_sm.render(line, True, palette.active["text_dim"]),
                    (12, y)
                )
                y += ROW_H

    # ── Panel Estación ───────────────────────────────────────────────────

    def _draw_station_panel(self, surf, station) -> None:
        y = HEADER_H + 2
        summary = station.get_summary()

        y = self._draw_section_label(surf, "DEMANDA", y)
        demand = station.pending_demand
        color = palette.active["text_bright"] if demand > 0 else palette.active["text_dim"]
        label = f"{demand} pendientes" if demand > 0 else f"{demand}"
        surf.blit(self._font_sm.render(label, True, color), (12, y))
        y += ROW_H

        platform_data = station.platform_snapshot_data()
        total_queue = sum(p['queue_total'] for p in platform_data)
        walking = len(station._walking)
        if total_queue > 0 or walking > 0:
            parts = []
            if total_queue > 0:
                parts.append(f"{total_queue} en fila")
            if walking > 0:
                parts.append(f"{walking} caminando")
            surf.blit(
                self._font_sm.render("  ·  ".join(parts), True, palette.active["text_dim"]),
                (12, y)
            )
            y += ROW_H

        y = self._draw_separator(surf, y)
        y = self._draw_section_label(surf, "FLUJO", y)
        surf.blit(
            self._font_sm.render(f"Pasajeros   {summary['passenger_rate']:.1f}/s",
                                 True, palette.active["text_bright"]),
            (12, y)
        )
        y += ROW_H
        surf.blit(
            self._font_sm.render(f"VMs         {summary['vm_request_rate']:.1f}/s",
                                 True, palette.active["text_dim"]),
            (12, y)
        )
        y += ROW_H

        y = self._draw_separator(surf, y)
        y = self._draw_section_label(surf, "DESTINOS", y)
        dests = summary.get('destinations', {})
        if dests:
            max_k = max(len(str(k)) for k in dests.keys())
            max_v = max(len(f"{v:.0%}") for v in dests.values())
            item_w = 1 + max_k + 1 + max_v  # "S" + id + ":" + pct
            items = [
                f"S{str(k).ljust(max_k)}:{f'{v:.0%}'.rjust(max_v)}"
                for k, v in dests.items()
            ]

            font_d = self._font_sm
            row_h_d = ROW_H
            cw = font_d.size("X")[0]
            cols = max(1, (PANEL_W - 24) // (cw * (item_w + 1)))
            rows_needed = (len(items) + cols - 1) // cols
            if rows_needed > 5:
                font_d = self._font_xs
                row_h_d = 14
                cw = font_d.size("X")[0]
                cols = max(1, (PANEL_W - 24) // (cw * (item_w + 1)))

            for i in range(0, len(items), cols):
                if y + row_h_d > PANEL_H - 4:
                    surf.blit(font_d.render("...", True, palette.active["text_dim"]), (12, y))
                    break
                surf.blit(
                    font_d.render(" ".join(items[i:i + cols]),
                                  True, palette.active["text_dim"]),
                    (12, y)
                )
                y += row_h_d
        else:
            surf.blit(
                self._font_sm.render("Sin datos aún", True, palette.active["text_dim"]),
                (12, y)
            )

    # ── Primitivas de sección ────────────────────────────────────────────

    def _draw_section_label(self, surf, label, y) -> int:
        y += SECTION_PAD
        surf.blit(self._font_sm.render(label, True, palette.active["text_dim"]), (8, y))
        return y + SECTION_LABEL_H

    def _draw_separator(self, surf, y) -> int:
        y += 3
        pygame.draw.line(surf, PANEL_BORDER, (8, y), (PANEL_W - 8, y), 1)
        return y + 4

    @staticmethod
    def _draw_bar(surf, x, y, width, height, fill) -> None:
        pygame.draw.rect(surf, PANEL_BORDER, (x, y, width, height), 1)
        fill_w = int((width - 2) * max(0.0, min(1.0, fill)))
        if fill_w > 0:
            pygame.draw.rect(surf, ACCENT, (x + 1, y + 1, fill_w, height - 2))

    # ── Helpers de contenido ─────────────────────────────────────────────

    def _get_title_subtitle(self, panel, loc) -> tuple[str, str]:
        if panel['kind'] == 'station':
            summary = loc['station'].get_summary()
            return (
                f"Estación S{summary['station_id']}",
                f"{summary['platforms']} andenes · {summary['active_platforms']} activos",
            )
        vm = panel['ref']
        return f"VM #{vm.vehicle_id}", self._location_text(loc)

    @staticmethod
    def _location_text(loc) -> str:
        t = loc['template']
        if t == 'belt':
            return f"Belt · Slot {loc['slot_index']}"
        if t == 'tree':
            return f"Árbol {loc['track'].direction.value} · {loc['progress']*100:.0f}%"
        if t == 'lane':
            return f"BoardingLane · {loc['progress']*100:.0f}%"
        return ""

    @staticmethod
    def _vm_state_color(vm, loc) -> tuple:
        if loc['template'] == 'lane' and not loc['data'].get('boarding_committed', True):
            return palette.active["vm_boarding"]
        if vm.has_destination:
            return palette.active["vm_dest"]
        return palette.active["vm_default"]

    @staticmethod
    def _vm_velocity(loc) -> float:
        t = loc['template']
        if t == 'belt':
            return TRAIN_SPEED
        if t == 'lane':
            return BOARDING_LANE_SPEED
        return loc['data']['velocity']


    @staticmethod
    def _friendly_state(vm, loc) -> str:
        t = loc['template']
        if t == 'lane':
            return "Embarcando" if not loc['data'].get('boarding_committed', True) else "Comprometido"
        if t == 'tree':
            return "Ascendiendo" if loc['track'].direction.value == "UP" else "Descendiendo"
        return "Circulando"


    @staticmethod
    def _vm_label_lines(loc) -> list:
        if loc['template'] != 'belt':
            return []
        slot = loc['slot']
        lines = []
        if slot.get('destination_station_id') is not None:
            lines.append(f"Destino → S{slot['destination_station_id']}")
        if slot.get('demand_station_id') is not None:
            lines.append(f"Demanda → S{slot['demand_station_id']}")
        if slot.get('reserved_station_id') is not None:
            lines.append(f"Reserva → S{slot['reserved_station_id']}")
        if slot['colliding_vms']:
            lines.append(f"CHOQUE  {1 + len(slot['colliding_vms'])} VMs")
        return lines
