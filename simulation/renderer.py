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
from config.constants import TRAIN_SPACING, VM_RENDER_WIDTH, VM_RENDER_DEPTH, VM_RENDER_HEIGHT
from tracks.acceleration_tree import AccelerationTree
from tracks.boarding_lane import BoardingLane
from objects.types import TreeDirection

# ─── PALETA ──────────────────────────────────────────────────────────────────

BG            = (  8,  12,  18)    # fondo más profundo
BELT_GLOW     = (  0,  20,  80)    # halo azul eléctrico
BELT_CORE     = ( 30, 160, 255)    # azul brillante
UP_TREE       = ( 30, 200,  80)    # verde neón
DN_TREE       = (255,  60,  40)    # rojo vivo
LANE_COLOR    = ( 80, 200, 255)    # azul claro luminoso
JUNCTION_MARK = (200, 220, 255)    # blanco azulado
STATION_WIRE  = ( 60, 150, 255)    # azul medio
VM_FREE       = (150, 165, 185)    # gris azulado
VM_DEMAND     = (255, 190,  30)    # ámbar brillante
VM_DEST       = ( 40, 230, 110)    # verde menta
VM_RESERVED   = (210, 130, 255)    # violeta
VM_TRANSIT    = (255, 220,  60)    # amarillo dorado
VM_TRANSIT_GL = ( 60,  50,   0)    # glow dorado oscuro
VM_WIRE       = ( 70,  80,  95)    # aristas cuando no hay etiqueta
VM_PASSENGERS = (255, 255, 255)    # indicador interior cuando hay pasajeros
JUNCTION_DOT  = (255, 220,   0)    # punto amarillo de junction
HUD_BG        = (  8,  12,  20, 220)
HUD_LINE      = ( 30, 120, 255)
TEXT_BRIGHT   = (220, 230, 245)
TEXT_DIM      = ( 90, 105, 125)



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

    HUD_H = 90   # altura reservada para el panel HUD en píxeles

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
        self._draw_belt_vms(surface, camera, train, W, H)
        self._draw_tracks(surface, camera, network)
        self._draw_junction_markers(surface, camera, network, train)
        self._draw_stations(surface, camera, stations)
        self._draw_transit_vms(surface, camera, network)
        self._draw_hud(surface, train, current_time, fps, speed, paused, W, H)
        if paused:
            self._draw_pause_overlay(surface, W, H)

    # ── Belt ──────────────────────────────────────────────────────────────────

    def _draw_belt_rail(self, surface: pygame.Surface, camera, train) -> None:
        """
        Dibuja el rail del belt en dos capas:
            - Exterior grueso + oscuro → efecto de halo luminoso
            - Interior delgado + brillante → el rail propiamente dicho
        El belt va de X=0 a X=total_length, Y=0, Z=start_pos.z.
        """
        z  = train.start_pos.z
        p1 = camera.project(train.start_pos.x, train.start_pos.y, train.start_pos.z)
        p2 = camera.project(train.end_pos.x,   train.end_pos.y,   train.end_pos.z)
        if p1 and p2:
            sx1, sy1 = p1[0], p1[1]
            sx2, sy2 = p2[0], p2[1]
            pygame.draw.line(surface, BELT_GLOW, (sx1, sy1), (sx2, sy2), 7)
            pygame.draw.line(surface, BELT_CORE, (sx1, sy1), (sx2, sy2), 2)

    def _draw_belt_vms(
    self, surface: pygame.Surface, camera, train, W: int, H: int
    ) -> None:
        """
        Dibuja los VMs del belt como cajas wireframe 3D.

        LOD:
            depth > 1200 → invisible (sub-pixel, no dibuja)
            depth 400-1200 → punto de 1px coloreado por etiqueta dominante
            depth < 400   → caja wireframe completa con codificación por etiquetas
        """
        by = train.start_pos.y
        bz = train.start_pos.z

        for i, slot in enumerate(train.slots):
            if slot['vm'] is None:
                continue
            bx     = train.get_slot_belt_x(i)
            center = camera.project(bx, by, bz)
            if center is None:
                continue
            sx, sy, depth = center
            if sx < -50 or sx > W + 50 or sy < -50 or sy > H + 50:
                continue
            if depth > 1200:
                continue

            labels = self._active_label_colors(slot)

            if depth > 400:
                # Vista general: punto de 1px con color de etiqueta dominante
                dot_color = labels[0] if labels else VM_WIRE
                pygame.draw.circle(surface, dot_color, (sx, sy), 1)
            else:
                # Vista detallada: caja wireframe completa
                self._draw_vm_box(surface, camera, slot, bx, by, bz, depth, labels)

    def _draw_vm_box(
        self, surface, camera, slot, cx, cy, cz, depth, labels
    ) -> None:
        """
        Dibuja un VM como caja wireframe 3D con aristas coloreadas por etiquetas.

        Codificación visual:
            0 etiquetas : aristas grises uniformes
            1 etiqueta  : todas las aristas en ese color
            2 etiquetas : base = labels[0], techo = labels[1],
                        aristas verticales partidas en 2
            3 etiquetas : base = labels[0], techo = labels[2],
                        aristas verticales partidas en 3
        """
        hw = VM_RENDER_WIDTH  / 2
        hd = VM_RENDER_DEPTH  / 2
        ht = VM_RENDER_HEIGHT

        verts = [
            (cx-hw, cy-hd, cz),        # 0 base
            (cx+hw, cy-hd, cz),        # 1
            (cx+hw, cy+hd, cz),        # 2
            (cx-hw, cy+hd, cz),        # 3
            (cx-hw, cy-hd, cz + ht),   # 4 techo
            (cx+hw, cy-hd, cz + ht),   # 5
            (cx+hw, cy+hd, cz + ht),   # 6
            (cx-hw, cy+hd, cz + ht),   # 7
        ]
        pts = [camera.project(vx, vy, vz) for vx, vy, vz in verts]

        color_base = labels[0]  if labels else VM_WIRE
        color_top  = labels[-1] if labels else VM_WIRE

        # Aristas de la cara base
        for a, b in ((0,1),(1,2),(2,3),(3,0)):
            if pts[a] and pts[b]:
                pygame.draw.line(surface, color_base,
                                (pts[a][0], pts[a][1]), (pts[b][0], pts[b][1]), 1)

        # Aristas de la cara techo
        for a, b in ((4,5),(5,6),(6,7),(7,4)):
            if pts[a] and pts[b]:
                pygame.draw.line(surface, color_top,
                                (pts[a][0], pts[a][1]), (pts[b][0], pts[b][1]), 1)

        # Aristas verticales — partidas según número de etiquetas
        seg_colors = labels if labels else [VM_WIRE]
        for base_i, top_i in ((0,4),(1,5),(2,6),(3,7)):
            if pts[base_i] and pts[top_i]:
                pb = (pts[base_i][0], pts[base_i][1])
                pt = (pts[top_i][0],  pts[top_i][1])
                self._draw_split_edge(surface, pb, pt, seg_colors)

        # Indicador de pasajeros: punto blanco brillante en el centro de la caja
        if slot['vm'].passenger_count > 0:
            cp = camera.project(cx, cy, cz + ht / 2)
            if cp:
                r = max(1, int(400 / max(depth, 10)))
                pygame.draw.circle(surface, VM_PASSENGERS, (cp[0], cp[1]), r)

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
            - AccelerationTree UP  → verde
            - AccelerationTree DOWN → rojo
            - BoardingLane          → azul, 1px más grueso que los árboles
        """
        for track in network.tracks.values():
            if isinstance(track, AccelerationTree):
                color = UP_TREE if track.direction == TreeDirection.UP else DN_TREE
                width = 2
            else:  # BoardingLane
                color = LANE_COLOR
                width = 3
            self._draw_segment(
                surface, camera,
                track.start_pos.x, track.start_pos.y, track.start_pos.z,
                track.end_pos.x,   track.end_pos.y,   track.end_pos.z,
                color, width,
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

    # ── VMs en tránsito ───────────────────────────────────────────────────────

    def _draw_transit_vms(self, surface: pygame.Surface, camera, network) -> None:
        """
        Dibuja los VMs que están dentro de acceleration trees o boarding lanes.

        Normalmente son ~44 VMs — costo O(V × 12) despreciable.
        Cada VM se dibuja como caja wireframe 3D (1m × 1.5m × 1m).
        El glow exterior (caja más grande y oscura) da profundidad visual.

        Si la profundidad supera 800m la caja es sub-pixel → se dibuja como
        círculo (fallback visible en vista general).
        """
        VM_W, VM_D, VM_H = VM_RENDER_WIDTH, VM_RENDER_DEPTH, VM_RENDER_HEIGHT

        for track in network.tracks.values():
            for vm_id, data in track.vehicles.items():
                dist     = data['distance']
                progress = dist / track.length if track.length > 0 else 0.0
                pos        = track.position_at_progress(progress)
                cx, cy, cz = pos.x, pos.y, pos.z

                center = camera.project(cx, cy, cz)
                if center is None:
                    continue
                sx, sy, depth = center

                if depth > 800:
                    # Fallback: círculo de 3px cuando la caja sería sub-pixel
                    pygame.draw.circle(surface, VM_TRANSIT, (sx, sy), 3)
                    continue

                hw, hd, ht = VM_W / 2, VM_D / 2, VM_H
                verts = [
                    (cx - hw, cy - hd, cz),        # 0
                    (cx + hw, cy - hd, cz),        # 1
                    (cx + hw, cy + hd, cz),        # 2
                    (cx - hw, cy + hd, cz),        # 3
                    (cx - hw, cy - hd, cz + ht),   # 4
                    (cx + hw, cy - hd, cz + ht),   # 5
                    (cx + hw, cy + hd, cz + ht),   # 6
                    (cx - hw, cy + hd, cz + ht),   # 7
                ]
                # Glow: caja ligeramente más grande, color oscuro
                self._draw_wireframe_box(surface, camera, verts, VM_TRANSIT_GL, 5)
                # Caja principal
                self._draw_wireframe_box(surface, camera, verts, VM_TRANSIT, 1)

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_hud(
        self, surface, train, current_time, fps, speed, paused, W, H
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
        vel_str = "PAUSADO" if paused else f"{speed}×"

        # Columna izquierda
        for i, line in enumerate([
            f"t = {current_time:>9.1f} s",
            f"FPS: {fps:>4.0f}     Vel: {vel_str}",
            f"Belt: {on}/{total}    Tránsito: {transit}",
        ]):
            surf = self._font_sm.render(line, True, TEXT_BRIGHT)
            surface.blit(surf, (16, hud_y + 8 + i * 22))

        # Leyenda (columna derecha)
        lx = W - 220
        surface.blit(
            self._font_sm.render("Leyenda VM", True, TEXT_DIM), (lx, hud_y + 8)
        )
        for i, (label, color) in enumerate([
            ("Libre",        VM_FREE),
            ("Demanda",      VM_DEMAND),
            ("Destino",      VM_DEST),
            ("Reserva",      VM_RESERVED),
            ("En tránsito",  VM_TRANSIT),
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

    def _draw_segment(
        self, surface, camera,
        x1, y1, z1, x2, y2, z2,
        color, width=1,
    ) -> None:
        """
        Proyecta y dibuja un segmento 3D entre (x1,y1,z1) y (x2,y2,z2).
        Si algún extremo queda detrás de la cámara (project=None) no dibuja nada.
        """
        p1 = camera.project(x1, y1, z1)
        p2 = camera.project(x2, y2, z2)
        if p1 and p2:
            pygame.draw.line(surface, color, (p1[0], p1[1]), (p2[0], p2[1]), width)

    def _draw_wireframe_box(
        self, surface, camera, vertices, color, width=1
    ) -> None:
        """
        Proyecta una lista de 8 vértices 3D y dibuja las 12 aristas de la caja.
        Las aristas cuyos extremos no proyectan (detrás de cámara) se omiten.

        Parámetros
        ----------
        vertices : list de 8 tuplas (x, y, z) — orden: [0-3] base, [4-7] techo
        """
        pts = [camera.project(vx, vy, vz) for vx, vy, vz in vertices]
        for a, b in BOX_EDGES:
            if pts[a] and pts[b]:
                pygame.draw.line(
                    surface, color,
                    (pts[a][0], pts[a][1]),
                    (pts[b][0], pts[b][1]),
                    width,
                )

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