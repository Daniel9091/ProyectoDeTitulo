"""
renderer.py — Renderiza el estado de NSim en una superficie Pygame.

Responsabilidades:
    - Proyectar objetos 3D del mundo a 2D usando camera.project()
    - Culling básico: objetos detrás de la cámara (project devuelve None) se omiten
    - LOD para VMs en el belt: puntos coloreados por estado (escala con profundidad)
    - Wireframe 3D para VMs en tránsito y estaciones
    - HUD semitransparente en la parte inferior

Lo que NO hace:
    - No mueve objetos (responsabilidad de brain + tracks)
    - No maneja input (responsabilidad de camera)

Complejidad por frame (con ~3 estaciones, ~1549 VMs en belt, ~44 en tránsito):
    - Tracks     : O(T)       T ≈ 15, costo mínimo
    - Estaciones : O(S × 12) S ≈ 3, despreciable
    - VMs belt   : O(N)      N ≈ 1549, solo circle() con culling por viewport
    - VMs tráns. : O(V × 12) V ≈ 44, wireframe 3D — bajo
"""
import pygame
from config.constants import TRAIN_SPACING, VM_RENDER_WIDTH, VM_RENDER_DEPTH, VM_RENDER_HEIGHT, TRAIN_VM_LENGTH

from tracks.acceleration_tree import AccelerationTree
from tracks.boarding_lane import BoardingLane
from objects.types import TreeDirection

# ─── PALETA ──────────────────────────────────────────────────────────────────

# BG            = (  8,  12,  18)    # fondo más profundo
# BELT_GLOW     = (  0,  20,  80)    # halo azul eléctrico
# BELT_CORE     = ( 30, 160, 255)    # azul brillante
# UP_TREE       = ( 30, 200,  80)    # verde neón
# DN_TREE       = (255,  60,  40)    # rojo vivo
# LANE_COLOR    = ( 80, 200, 255)    # azul claro luminoso
# JUNCTION_MARK = (200, 220, 255)    # blanco azulado
# STATION_WIRE  = ( 60, 150, 255)    # azul medio
# VM_FREE       = (150, 165, 185)    # gris azulado
# VM_DEMAND     = (255, 190,  30)    # ámbar brillante
# VM_DEST       = ( 40, 230, 110)    # verde menta
# VM_RESERVED   = (210, 130, 255)    # violeta
# VM_TRANSIT    = (255, 220,  60)    # amarillo dorado
# VM_TRANSIT_GL = ( 60,  50,   0)    # glow dorado oscuro
# VM_COLLISION  = (255,   0,   0)    # rojo puro — choque: 2+ VMs en el mismo slot
# VM_WIRE       = ( 70,  80,  95)    # aristas cuando no hay etiqueta
# VM_PASSENGERS = (255, 255, 255)    # indicador interior cuando hay pasajeros
# JUNCTION_DOT  = (255, 220,   0)    # punto amarillo de junction
# HUD_BG        = (  8,  12,  20, 220)


BG            = (  8,  12,  18)    # fondo más profundo
TRACK_GLOW    = (  0,  20,  80)    # halo azul eléctrico — solo el belt lo usa
TRACK_COLOR   = ( 30, 160, 255)    # azul neón — TODOS los rieles: belt, árboles, lanes
JUNCTION_MARK = (200, 220, 255)    # blanco azulado
STATION_WIRE  = ( 60, 90, 220)    # azul medio
VM_DEFAULT    = (  190, 225, 250)    # sky blue neón — VM sin ninguna etiqueta activa
VM_DEFAULT_GL = (  40,  70,  70)    # glow oscuro a juego, halo de VMs en tránsito
VM_DEMAND     = (255, 225,   0)    # amarillo neón — etiqueta de demanda
VM_BOARDING   = (255, 130,   0)    # naranjo neón — pasajeros abordando
VM_RESERVED   = (215,  175, 250)    # violeta reforzado — etiqueta de reserva
VM_DEST       = ( 40, 255, 120)    # verde neón — etiqueta de destino
VM_COLLISION  = (255,   0,   0)    # rojo puro — choque: 2+ VMs en el mismo slot
VM_PASSENGERS = (255, 255, 255)    # indicador interior cuando hay pasajeros
JUNCTION_DOT  = (255, 220,   0)    # punto amarillo de junction

HUD_BG        = (  8,  12,  20, 220)
HUD_LINE      = ( 30, 120, 255)
TEXT_BRIGHT   = (220, 230, 245)
TEXT_DIM      = (165, 180, 200)

# Pares de índices para las 12 aristas de una caja con vértices [0-3]=base, [4-7]=techo
BOX_EDGES = [
    (0, 1), (1, 2), (2, 3), (3, 0),   # cara base
    (4, 5), (5, 6), (6, 7), (7, 4),   # cara techo
    (0, 4), (1, 5), (2, 6), (3, 7),   # aristas verticales
]


class Renderer:
    """
    Renderizador 3D con proyección perspectiva.

    No almacena estado de simulación — todo se recibe por render().
    El único estado interno son las fuentes (cacheadas para no recrearlas cada frame).

    Uso:
        renderer = Renderer(font_sm, font_md)
        renderer.render(surface, camera, train, network, stations,
                        current_time, fps, speed, paused)
    """

    HUD_H = 134   # altura reservada para el panel HUD en píxeles

    def __init__(self, font_sm: pygame.font.Font, font_md: pygame.font.Font):
        self._font_sm = font_sm
        self._font_md = font_md
        self.show_legend = True 

    # ── API pública ───────────────────────────────────────────────────────────

    def render(
        self,
        surface:      pygame.Surface,
        camera,
        train,
        network,
        stations:     dict,
        current_time: float,
        fps:          float,
        speed:        int,
        paused:       bool,
    ) -> None:
        """
        Dibuja un frame completo.

        Orden de dibujado (de fondo a frente):
            1. Fondo liso
            2. Rail del belt (doble capa para efecto de brillo)
            3. VMs sobre el belt (LOD basado en profundidad)
            4. Tracks: árboles UP/DOWN y boarding lanes
            5. Marcadores en los junctions
            6. Wireframe 3D de las estaciones
            7. Wireframe 3D de VMs en tránsito
            8. Panel HUD
            9. Overlay de pausa (si aplica)
        """
        W, H = surface.get_size()
        surface.fill(BG)

        self._draw_belt_rail(surface, camera, train)
        belt_drawn = self._draw_belt_vms(surface, camera, train, W, H)
        self._draw_tracks(surface, camera, network)
        self._draw_junction_markers(surface, camera, network, train)
        self._draw_stations(surface, camera, stations)
        self._draw_walking_passengers(surface, camera, stations, W, H)
        transit_drawn, transit_collisions = self._draw_transit_vms(surface, camera, network, W, H)
        self._draw_hud(surface, train, current_time, fps, speed, paused, W, H,
                        belt_drawn, transit_drawn, transit_collisions)

        if paused:
            self._draw_pause_overlay(surface, W, H)

    # ── Belt ──────────────────────────────────────────────────────────────────

    def _draw_belt_rail(self, surface: pygame.Surface, camera, train) -> None:
        """
        Dibuja el rail del belt en dos capas:
            - Exterior grueso + oscuro → efecto de halo luminoso
            - Interior delgado + brillante → el rail propiamente dicho
        El belt va de X=0 a X=total_length, Y=0, Z=start_pos.z.
        Usa project_segment (no project) porque el belt es muy largo: sin
        recorte contra el near-clip, un extremo detrás de cámara borra el
        rail completo en vez de solo la parte que corresponde.
        """
        seg = camera.project_segment(
            train.start_pos.x, train.start_pos.y, train.start_pos.z,
            train.end_pos.x,   train.end_pos.y,   train.end_pos.z,
        )
        if seg:
            p1, p2 = seg
            pygame.draw.line(surface, TRACK_GLOW, p1, p2, 7)
            pygame.draw.line(surface, TRACK_COLOR, p1, p2, 2)

    def _draw_belt_vms(
    self, surface: pygame.Surface, camera, train, W: int, H: int
    ) -> int:
        """
        Dibuja los VMs del belt como cajas wireframe 3D.

        LOD:
            depth > 1200 → invisible (sub-pixel, no dibuja)
            depth 400-1200 → punto de 1px coloreado por etiqueta dominante
            depth < 400   → caja wireframe completa con codificación por etiquetas
        + Retorna la cantidad de VMs dibujados este frame.
        """

        by = train.start_pos.y
        bz = train.start_pos.z
        drawn = 0

        for i, slot in enumerate(train.slots):
            if slot['vm'] is None:
                continue
            bx     = train.get_slot_belt_x(i)
            center = self._project_visible(camera, bx, by, bz, W, H)
            if center is None:
                continue
            sx, sy, depth = center
            if slot['colliding_vms']:
                # Choque: siempre caja completa, nunca punto ni invisible por LOD
                drawn += 1
                self._draw_collision_stack(surface, camera, slot, bx, by, bz)
                continue
            drawn += 1

            labels = self._active_label_colors(slot)


            if depth > 400:
                # Vista general: punto de 1px con color de etiqueta dominante
                dot_color = labels[0] if labels else VM_DEFAULT
                pygame.draw.circle(surface, dot_color, (sx, sy), 1)
            else:
                # Vista detallada: caja wireframe completa
                self._draw_vm_box(surface, camera, slot['vm'], bx, by, bz, labels)


        return drawn

    def _draw_vm_box(
        self, surface, camera, vm, cx, cy, cz, labels
    ) -> None:
        """
        Dibuja un VM como caja wireframe 3D con aristas coloreadas por etiquetas.
        La usan tanto el belt como los VMs en tránsito (árboles/lanes) — el color
        es siempre función del estado actual del VM, nunca de dónde está parado.
        """
        hw = VM_RENDER_WIDTH  / 2
        hd = VM_RENDER_DEPTH  / 2
        ht = VM_RENDER_HEIGHT

        verts = [
            (cx-hw, cy-hd, cz),
            (cx+hw, cy-hd, cz),
            (cx+hw, cy+hd, cz),
            (cx-hw, cy+hd, cz),
            (cx-hw, cy-hd, cz + ht),
            (cx+hw, cy-hd, cz + ht),
            (cx+hw, cy+hd, cz + ht),
            (cx-hw, cy+hd, cz + ht),
        ]
        pts = [camera.project(vx, vy, vz) for vx, vy, vz in verts]

        color_base = labels[0]  if labels else VM_DEFAULT
        color_top  = labels[-1] if labels else VM_DEFAULT

        for a, b in ((0,1),(1,2),(2,3),(3,0)):
            if pts[a] and pts[b]:
                pygame.draw.line(surface, color_base,
                                (pts[a][0], pts[a][1]), (pts[b][0], pts[b][1]), 1)

        for a, b in ((4,5),(5,6),(6,7),(7,4)):
            if pts[a] and pts[b]:
                pygame.draw.line(surface, color_top,
                                (pts[a][0], pts[a][1]), (pts[b][0], pts[b][1]), 1)

        seg_colors = labels if labels else [VM_DEFAULT]
        for base_i, top_i in ((0,4),(1,5),(2,6),(3,7)):
            if pts[base_i] and pts[top_i]:
                pb = (pts[base_i][0], pts[base_i][1])
                pt = (pts[top_i][0],  pts[top_i][1])
                self._draw_split_edge(surface, pb, pt, seg_colors)

        self._draw_passenger_dot(surface, camera, vm, cx, cy, cz + ht / 2, pts)

    def _draw_passenger_dot(self, surface, camera, vm, cx, cy, top_z, pts) -> None:
        """
        Punto blanco pequeño sobre la caja del VM, visible solo si lleva
        pasajeros. El radio escala con el ancho EN PANTALLA de la propia caja
        (15%, tope 4px) — nunca se sale de sus bordes, a cualquier distancia.
        """
        if vm.passenger_count <= 0:
            return
        cp = camera.project(cx, cy, top_z)
        if cp is None or pts[0] is None or pts[1] is None:
            return
        box_w = abs(pts[1][0] - pts[0][0])
        r = max(1, min(4, int(box_w * 0.15)))
        pygame.draw.circle(surface, VM_PASSENGERS, (cp[0], cp[1]), r)


    def _draw_collision_stack(
        self, surface, camera, slot, cx, cy, cz
    ) -> None:
        """
        Dibuja todos los VMs de un slot en choque como una torre de cajas rojas
        apiladas en Z — visualiza que más de un VM cayó en el mismo slot.
        """
        all_vms = [slot['vm']] + slot['colliding_vms']
        for i, vm in enumerate(all_vms):
            self._draw_vm_box(
                surface, camera, vm,
                cx, cy, cz + i * VM_RENDER_HEIGHT,
                [VM_COLLISION],
            )

    @staticmethod
    def _draw_split_edge(
        surface: pygame.Surface,
        p_bottom: tuple,
        p_top:    tuple,
        colors:   list,
    ) -> None:
        """
        Dibuja una arista vertical partida en len(colors) segmentos.

        p_bottom, p_top : coordenadas 2D (sx, sy) del extremo inferior y superior
        colors          : lista de 1-3 colores, uno por segmento (abajo → arriba)
        """
        n = len(colors)
        if n == 1:
            pygame.draw.line(surface, colors[0], p_bottom, p_top, 1)
            return
        # Calcular los puntos intermedios en espacio de pantalla
        pts = [p_bottom]
        for i in range(1, n):
            t = i / n
            mid = (
                int(p_bottom[0] + (p_top[0] - p_bottom[0]) * t),
                int(p_bottom[1] + (p_top[1] - p_bottom[1]) * t),
            )
            pts.append(mid)
        pts.append(p_top)
        for i in range(n):
            pygame.draw.line(surface, colors[i], pts[i], pts[i+1], 1)

    # ── Tracks ────────────────────────────────────────────────────────────────

    def _draw_tracks(self, surface: pygame.Surface, camera, network) -> None:
        """
        Dibuja todos los tracks de la red como segmentos 3D:
        """
        for track in network.tracks.values():
            width = 2 if isinstance(track, AccelerationTree) else 3
            self._draw_segment(
                surface, camera,
                track.start_pos.x, track.start_pos.y, track.start_pos.z,
                track.end_pos.x,   track.end_pos.y,   track.end_pos.z,
                TRACK_COLOR, width,
            )

    # ── Junction markers ──────────────────────────────────────────────────────

    def _draw_junction_markers(
        self, surface: pygame.Surface, camera, network, train
    ) -> None:
        """
        Punto amarillo sólido en cada junction (unión exacta belt-árbol).
        Sin círculo, solo el punto.
        """
        by = train.start_pos.y
        bz = train.start_pos.z
        for jmap in (network.junctions_up, network.junctions_down):
            for junction in jmap.values():
                result = camera.project(junction.belt_x, by, bz)
                if result:
                    sx, sy, depth = result
                    r = max(1, min(3, int(600 / max(depth, 80))))
                    pygame.draw.circle(surface, JUNCTION_DOT, (sx, sy), r)

    # ── Estaciones ────────────────────────────────────────────────────────────

    def _draw_stations(
        self, surface: pygame.Surface, camera, stations: dict
    ) -> None:
        """
        Dibuja cada estación como caja wireframe 3D.

        Dimensiones de la caja:
            X : origin.x ± x_length/2
            Y : origin.y ± y_length/2
            Z : origin.z → origin.z + floor_height

        Etiqueta flotante 5m por encima de la caja.
        """
        for station in stations.values():
            ox, oy, oz = station.origin.x, station.origin.y, station.origin.z
            hw = station.dimensions.x_length  / 2.0
            hl = station.dimensions.y_length  / 2.0
            ht = station.dimensions.floor_height

            # 8 vértices del prisma: [0-3] base, [4-7] techo
            verts = [
                (ox - hw, oy - hl, oz),        # 0
                (ox + hw, oy - hl, oz),        # 1
                (ox + hw, oy + hl, oz),        # 2
                (ox - hw, oy + hl, oz),        # 3
                (ox - hw, oy - hl, oz + ht),   # 4
                (ox + hw, oy - hl, oz + ht),   # 5
                (ox + hw, oy + hl, oz + ht),   # 6
                (ox - hw, oy + hl, oz + ht),   # 7
            ]
            self._draw_wireframe_box(surface, camera, verts, STATION_WIRE, 1)

            # Etiqueta encima de la caja
            lbl_pt = camera.project(ox, oy, oz + ht + 8)
            if lbl_pt:
                txt = self._font_md.render(f"S{station.station_id}", True, STATION_WIRE)
                surface.blit(txt, (lbl_pt[0] - txt.get_width() // 2, lbl_pt[1] - 8))

    def _draw_walking_passengers(
        self, surface: pygame.Surface, camera, stations: dict, W: int, H: int
    ) -> None:
        """
        Punto pequeño por cada pasajero caminando desde el centro de la
        estación hacia su boarding lane asignada. Interpola linealmente su
        posición 3D según el progreso (distance / walk_distance).
        """
        for station in stations.values():
            origin = station.origin
            for data in station._walking.values():
                lane = data['target_lane']
                t = 1.0 if data['walk_distance'] <= 0 else min(1.0, data['distance'] / data['walk_distance'])
                px = origin.x + (lane.start_pos.x - origin.x) * t
                py = origin.y + (lane.start_pos.y - origin.y) * t
                pz = origin.z + (lane.start_pos.z - origin.z) * t
                center = self._project_visible(camera, px, py, pz, W, H, margin=20)
                if center is None:
                    continue
                sx, sy, _ = center
                pygame.draw.circle(surface, VM_PASSENGERS, (sx, sy), 2)

    # ── VMs en tránsito ───────────────────────────────────────────────────────

    def _draw_transit_vms(self, surface: pygame.Surface, camera, network, W: int, H: int) -> tuple[int, int]:
        """
        Dibuja los VMs que están dentro de acceleration trees o boarding lanes.

        Color, en orden de prioridad:
            1. Chocando (2+ VMs a menos de TRAIN_VM_LENGTH en el mismo track) → rojo
            2. Abordando activamente (antes de boarding_committed) → naranjo
            3. Con destino asignado → verde
            4. Ninguna de las anteriores → VM_DEFAULT

        Retorna (VMs dibujados, VMs en choque) este frame.
        """
        VM_W, VM_D, VM_H = VM_RENDER_WIDTH, VM_RENDER_DEPTH, VM_RENDER_HEIGHT
        drawn = 0
        collisions = 0
        for track in network.tracks.values():
            is_lane = isinstance(track, BoardingLane)
            items = list(track.vehicles.items())
            colliding_ids = self._find_colliding_vehicle_ids(items)

            for vm_id, data in items:
                vm = data['vehicle']
                dist     = data['distance']
                progress = dist / track.length if track.length > 0 else 0.0
                pos        = track.position_at_progress(progress)
                cx, cy, cz = pos.x, pos.y, pos.z

                center = self._project_visible(camera, cx, cy, cz, W, H)
                if center is None:
                    continue
                sx, sy, depth = center
                drawn += 1

                if vm_id in colliding_ids:
                    collisions += 1
                    labels = [VM_COLLISION]
                else:
                    is_actively_boarding = is_lane and not data['boarding_committed']
                    labels = self._transit_label_colors(vm, is_actively_boarding)

                if depth > 800:
                    color = labels[0] if labels else VM_DEFAULT
                    pygame.draw.circle(surface, color, (sx, sy), 3)
                    continue

                hw, hd, ht = VM_W / 2, VM_D / 2, VM_H
                verts = [
                    (cx - hw, cy - hd, cz),
                    (cx + hw, cy - hd, cz),
                    (cx + hw, cy + hd, cz),
                    (cx - hw, cy + hd, cz),
                    (cx - hw, cy - hd, cz + ht),
                    (cx + hw, cy - hd, cz + ht),
                    (cx + hw, cy + hd, cz + ht),
                    (cx - hw, cy + hd, cz + ht),
                ]
                self._draw_wireframe_box(surface, camera, verts, VM_DEFAULT_GL, 5)
                self._draw_vm_box(surface, camera, vm, cx, cy, cz, labels)
        return drawn, collisions

    @staticmethod
    def _find_colliding_vehicle_ids(items: list) -> set:
        """
        Detecta pares de VMs en el mismo track (árbol o lane) cuya distancia
        recorrida difiere menos que TRAIN_VM_LENGTH — equivalente a un choque
        del belt, pero para tracks continuos sin slots discretos.
        """
        colliding = set()
        for i in range(len(items)):
            id_a, data_a = items[i]
            for j in range(i + 1, len(items)):
                id_b, data_b = items[j]
                if abs(data_a['distance'] - data_b['distance']) < TRAIN_VM_LENGTH:
                    colliding.add(id_a)
                    colliding.add(id_b)
        return colliding

    @staticmethod
    def _transit_label_colors(vm, is_actively_boarding: bool) -> list:
        """
        Mientras el VM está embarcando pasajeros (antes de boarding_committed)
        se pinta naranjo puro, sin mezclar con destino aunque ya lo tenga
        asignado internamente. Al comprometerse el embarque, cambia a verde
        puro si tiene destino, o al color por defecto si no.
        """
        if is_actively_boarding:
            return [VM_BOARDING]
        if vm.has_destination:
            return [VM_DEST]
        return []


    # ── HUD ───────────────────────────────────────────────────────────────────
    def _draw_hud(
        self, surface, train, current_time, fps, speed, paused, W, H,
        belt_drawn, transit_drawn, transit_collisions,
    ) -> None:
        """
        Panel semitransparente en la parte inferior con:
            - Columna izquierda : métricas de simulación
            - Columna derecha   : leyenda de colores de VMs
            - Línea inferior    : atajos de teclado
        """
        hud_y = H - self.HUD_H

        panel = pygame.Surface((W, self.HUD_H), pygame.SRCALPHA)
        panel.fill(HUD_BG)
        surface.blit(panel, (0, hud_y))
        pygame.draw.line(surface, HUD_LINE, (0, hud_y), (W, hud_y), 1)

        on      = sum(1 for s in train.slots if s['vm'] is not None)
        total   = train.max_slots
        transit = total - on
        collisions = train.get_colliding_vm_count() + transit_collisions
        vel_str = "PAUSADO" if paused else f"{speed}×"

        # Columna izquierda
        for i, line in enumerate([
            f"t = {current_time:>9.1f} s",
            f"FPS: {fps:>4.0f}     Vel: {vel_str}",
            f"Belt: {on}/{total}    Tránsito: {transit}",
            f"Visibles: {belt_drawn + transit_drawn}  (belt {belt_drawn}/{on}  ·  tránsito {transit_drawn}/{transit})",
            f"Colisiones: {collisions}",
        ]):


            surf = self._font_sm.render(line, True, TEXT_BRIGHT)
            surface.blit(surf, (16, hud_y + 8 + i * 22))

        # Leyenda (columna derecha)
        lx = W - 220
        surface.blit(
            self._font_sm.render("Leyenda VM", True, TEXT_DIM), (lx, hud_y + 8)
        )
        for i, (label, color) in enumerate([
            ("Normal",       VM_DEFAULT),
            ("Demanda",      VM_DEMAND),
            ("Abordando",    VM_BOARDING),
            ("Reserva",      VM_RESERVED),
            ("Destino",      VM_DEST),
            ("Choque",       VM_COLLISION),
        ]):
            cy = hud_y + 26 + i * 13
            pygame.draw.circle(surface, color, (lx + 6, cy + 5), 5)
            surface.blit(self._font_sm.render(label, True, TEXT_DIM), (lx + 16, cy))

        # Controles
        ctrl = (
            "WASD=mover   ←→↑↓=rotar   QE=altura   ZX=zoom   "
            "Clic der=look   H=reset   Espacio=pausa   1234=vel   Esc=salir"
        )
        cs = self._font_sm.render(ctrl, True, TEXT_DIM)
        surface.blit(cs, (W // 2 - cs.get_width() // 2, hud_y + self.HUD_H - 18))

    def _draw_pause_overlay(self, surface, W, H) -> None:
        """Overlay semitransparente con texto PAUSADO centrado en pantalla."""
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        surface.blit(overlay, (0, 0))
        txt = self._font_md.render(
            "PAUSADO  —  Espacio para continuar", True, TEXT_BRIGHT
        )
        surface.blit(txt, (W // 2 - txt.get_width() // 2, H // 2 - 12))

    # ── Primitivas internas ───────────────────────────────────────────────────

    def _project_visible(
        self, camera, x: float, y: float, z: float, W: int, H: int, margin: int = 50
    ):
        """
        Proyecta un punto 3D y aplica cull de viewport.

        Retorna (sx, sy, depth) si el punto cae dentro de la pantalla
        (con margen), o None si está detrás de la cámara o fuera de vista.
        Único criterio de "visible" para VMs — el resto de objetos no lo usa.
        """
        center = camera.project(x, y, z)
        if center is None:
            return None
        sx, sy, depth = center
        if sx < -margin or sx > W + margin or sy < -margin or sy > H + margin:
            return None
        return center

    def _draw_segment(
        self, surface, camera,
        x1, y1, z1, x2, y2, z2,
        color, width=1,
    ) -> None:
        """
        Proyecta y dibuja un segmento 3D entre (x1,y1,z1) y (x2,y2,z2).
        Recorta contra el near-clip plane si solo un extremo está detrás de
        cámara — el segmento solo se omite por completo si ambos lo están.
        """
        seg = camera.project_segment(x1, y1, z1, x2, y2, z2)
        if seg:
            p1, p2 = seg
            pygame.draw.line(surface, color, p1, p2, width)


    def _draw_wireframe_box(
        self, surface, camera, vertices, color, width=1
    ) -> None:
        """
        Proyecta una lista de 8 vértices 3D y dibuja las 12 aristas de la caja.
        Cada arista se recorta contra el near-clip plane si solo uno de sus
        dos vértices está detrás de cámara — solo se omite si ambos lo están.

        Parámetros
        ----------
        vertices : list de 8 tuplas (x, y, z) — orden: [0-3] base, [4-7] techo
        """
        for a, b in BOX_EDGES:
            xa, ya, za = vertices[a]
            xb, yb, zb = vertices[b]
            seg = camera.project_segment(xa, ya, za, xb, yb, zb)
            if seg:
                p1, p2 = seg
                pygame.draw.line(surface, color, p1, p2, width)

    @staticmethod
    def _active_label_colors(slot: dict) -> list:
        """
        Retorna la lista de colores de etiquetas activas en orden de prioridad.
        Máximo 3 elementos — uno por etiqueta activa.
        """
        colors = []
        if slot.get('reserved_station_id')   is not None: colors.append(VM_RESERVED)
        if slot.get('destination_station_id') is not None: colors.append(VM_DEST)
        if slot.get('demand_station_id')      is not None: colors.append(VM_DEMAND)
        return colors

    @staticmethod
    def _slot_color(slot: dict) -> tuple:
        """
        Color aditivo por etiquetas activas.
        Cada etiqueta suma su componente RGB — slots con múltiples etiquetas
        aparecen más brillantes. Sin etiqueta → gris suave (VM_FREE).
        """
        r = g = b = 0
        if slot.get('reserved_station_id')   is not None: r += 188; g += 140; b += 255
        if slot.get('destination_station_id') is not None: r +=  60; g += 200; b += 120
        if slot.get('demand_station_id')      is not None: r += 210; g += 160; b +=  30
        if r == 0 and g == 0 and b == 0:
            return VM_FREE
        return (min(255, r), min(255, g), min(255, b))