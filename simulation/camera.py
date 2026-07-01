"""
camera.py — Cámara 3D con proyección perspectiva para NSim.

Responsabilidades:
    - Mantener el estado de la cámara: posición, orientación (yaw/pitch) y FOV.
    - Proyectar coordenadas 3D del mundo a píxeles 2D de pantalla usando
      perspectiva estándar (no ortográfica).
    - Procesar entrada del usuario: movimiento continuo (teclado), mouse look
      (click derecho + arrastre), zoom (scroll/teclas), reset (H).
    - NO dibuja nada — solo transforma coordenadas.

Sistema de coordenadas del mundo (NSim):
    X : eje del belt, positivo hacia la derecha (~3000 m de rango)
    Y : eje perpendicular al belt, positivo hacia el "frente" de la pantalla
    Z : altura, positivo hacia arriba (belt en Z≈-15, estaciones en Z≈0..5)

Orientación de la cámara:
    Yaw   (θ): rotación alrededor del eje Z global.
               0° = mirando en dirección +X
               90° = mirando en dirección +Y
    Pitch (α): inclinación arriba/abajo.
               0° = horizontal, +° = mirando hacia arriba, −° = hacia abajo.
               Limitado a ±CAM_PITCH_LIMIT para evitar gimbal lock.

Matemática de proyección (ver Camera.project):
    El punto del mundo se transforma al espacio de la cámara mediante
    producto punto con los ejes {right, up, forward} de la cámara.
    Luego se aplica división perspectiva estándar.

Controles:
    W / S             : avanzar / retroceder (en plano XY, sin cambiar Z)
    A / D             : desplazamiento lateral
    Q / E             : subir / bajar (eje Z)
    ← →               : rotar yaw (continuo)
    ↑ ↓               : rotar pitch (continuo)
    Z / X             : zoom (FOV −/+)
    Scroll            : zoom hacia el cursor (rápido)
    Click derecho drag: mouse look estilo FPS
    H                 : reset a la posición y orientación iniciales
"""

import math
import pygame
from config.constants import (
    CAM_FOV_DEFAULT, CAM_FOV_MIN, CAM_FOV_MAX,
    CAM_NEAR_CLIP, CAM_MOVE_SPEED, CAM_ROT_SPEED,
    CAM_MOUSE_SENS, CAM_ZOOM_KEY_SPEED, CAM_PITCH_LIMIT,
    SCREEN_WIDTH, SCREEN_HEIGHT,
)

class Camera:
    """
    Cámara 3D con perspectiva para explorar el mundo de NSim.

    Uso típico en main.py:
        camera = Camera(screen_w, screen_h, pos=[1500, -600, 250], yaw=90, pitch=-20)
        # En el loop:
        camera.update(dt)
        for event in events:
            camera.handle_event(event)
        # En el renderer:
        result = camera.project(world_x, world_y, world_z)
        if result:
            sx, sy, depth = result
    """
    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        pos:   list  = None,
        yaw:   float = 90.0,
        pitch: float = -20.0,
        fov:   float = CAM_FOV_DEFAULT,
    ):
        """
        Parámetros
        ----------
        screen_w, screen_h : dimensiones de la ventana Pygame (px)
        pos   : [x, y, z] posición inicial de la cámara en el mundo (m)
        yaw   : orientación horizontal inicial (°). 90° = mirando en +Y.
        pitch : inclinación inicial (°). Negativo = mirando hacia abajo.
        fov   : campo de visión inicial (°).
        """
        self.screen_w = screen_w
        self.screen_h = screen_h
        # Estado actual
        self.pos   = list(pos) if pos else [1500.0, -600.0, 250.0]
        self.yaw   = float(yaw)
        self.pitch = float(pitch)
        self.fov   = float(fov)

        # Guardamos el estado inicial para el reset
        self._init_pos   = list(self.pos)
        self._init_yaw   = self.yaw
        self._init_pitch = self.pitch
        self._init_fov   = self.fov

        # Estado interno de mouse look
        self._mouse_look  = False
        self._last_mouse  = None

        # Factor de escala perspectiva — se recalcula cuando cambia el FOV
        self._fov_scale   = 0.0
        self._recompute_fov_scale()

        # ── API principal ─────────────────────────────────────────────────────────

    def project(
        self, wx: float, wy: float, wz: float
    ) -> tuple[int, int, float] | None:
        """
        Proyecta un punto 3D del mundo a coordenadas de pantalla 2D.

        Matemática:
            1. delta = punto_mundo − posición_cámara
            2. x_cam, y_cam, z_cam = proyección de delta sobre los ejes
               {right, up, forward} de la cámara (ver módulo docstring).
            3. Si z_cam < CAM_NEAR_CLIP el punto está detrás → retorna None.
            4. División perspectiva:
                   sx = cx + fov_scale * x_cam / z_cam
                   sy = cy − fov_scale * y_cam / z_cam   (Y invertido en Pygame)

        Retorna
        -------
        (screen_x, screen_y, depth) si el punto es visible, None si está
        detrás de la cámara o demasiado cerca del plano near clip.
        """
        dx = wx - self.pos[0]
        dy = wy - self.pos[1]
        dz = wz - self.pos[2]

        yaw_r   = math.radians(self.yaw)
        pitch_r = math.radians(self.pitch)
        cos_y   = math.cos(yaw_r);   sin_y = math.sin(yaw_r)
        cos_p   = math.cos(pitch_r); sin_p = math.sin(pitch_r)

        # Proyección sobre el eje RIGHT de la cámara = (sin_y, −cos_y, 0)
        x_cam = dx * sin_y - dy * cos_y

        # h: componente de delta en la dirección horizontal forward (XY)
        # Sirve de puente para calcular y_cam y z_cam eficientemente.
        h     =  dx * cos_y + dy * sin_y

        # Proyección sobre UP = (−cos_y·sin_p, −sin_y·sin_p, cos_p)
        y_cam = -h * sin_p + dz * cos_p

        # Profundidad: proyección sobre FORWARD = (cos_y·cos_p, sin_y·cos_p, sin_p)
        z_cam =  h * cos_p + dz * sin_p

        if z_cam < CAM_NEAR_CLIP:
            return None  # punto detrás de la cámara — no renderizar

        inv_depth = 1.0 / z_cam   # división perspectiva
        cx = self.screen_w / 2
        cy = self.screen_h / 2
        sx = int(cx + self._fov_scale * x_cam * inv_depth)
        sy = int(cy - self._fov_scale * y_cam * inv_depth)

        return sx, sy, z_cam
    
    def update(self, dt: float) -> None:
        """
        Aplica movimiento continuo basado en el estado actual del teclado.
        Debe llamarse CADA FRAME, pasando dt en segundos.

        Diseño de controles:
            W/S mueven en la proyección horizontal del forward (no cambia Z
            aunque la cámara mire hacia abajo), para evitar que el jugador
            "vuele" al avanzar. Q/E controlan Z de forma independiente.
        """
        keys  = pygame.key.get_pressed()
        spd   = CAM_MOVE_SPEED * dt
        rot   = CAM_ROT_SPEED  * dt

        yaw_r = math.radians(self.yaw)
        cos_y = math.cos(yaw_r)
        sin_y = math.sin(yaw_r)

        # Dirección horizontal de la cámara (sin componente Z)
        fwd_x, fwd_y =  cos_y, sin_y
        rgt_x, rgt_y =  sin_y, -cos_y

        # Traslación
        if keys[pygame.K_w]: self.pos[0] += fwd_x * spd; self.pos[1] += fwd_y * spd
        if keys[pygame.K_s]: self.pos[0] -= fwd_x * spd; self.pos[1] -= fwd_y * spd
        if keys[pygame.K_d]: self.pos[0] += rgt_x * spd; self.pos[1] += rgt_y * spd
        if keys[pygame.K_a]: self.pos[0] -= rgt_x * spd; self.pos[1] -= rgt_y * spd
        if keys[pygame.K_e] or keys[pygame.K_PAGEUP]:   self.pos[2] += spd
        if keys[pygame.K_q] or keys[pygame.K_PAGEDOWN]: self.pos[2] -= spd

        # Rotación con teclado
        if keys[pygame.K_LEFT]:  self.yaw   -= rot
        if keys[pygame.K_RIGHT]: self.yaw   += rot
        if keys[pygame.K_UP]:
            self.pitch = min(CAM_PITCH_LIMIT,  self.pitch + rot)
        if keys[pygame.K_DOWN]:
            self.pitch = max(-CAM_PITCH_LIMIT, self.pitch - rot)

        # Zoom con teclas
        if keys[pygame.K_z]:
            self.fov = max(CAM_FOV_MIN, self.fov - CAM_ZOOM_KEY_SPEED * dt)
            self._recompute_fov_scale()
        if keys[pygame.K_x]:
            self.fov = min(CAM_FOV_MAX, self.fov + CAM_ZOOM_KEY_SPEED * dt)
            self._recompute_fov_scale()    

    def handle_event(self, event: pygame.event.Event) -> None:
        """
        Procesa un evento de Pygame.

        Mouse look (click derecho + arrastre):
            Oculta el cursor del sistema mientras está activo.
            El cursor se restaura al soltar el botón.

        Zoom con scroll:
            Cambia el FOV directamente — efecto instantáneo.
        """
        if event.type == pygame.MOUSEWHEEL:
            self.fov = max(CAM_FOV_MIN, min(CAM_FOV_MAX, self.fov - event.y * 3.0))
            self._recompute_fov_scale()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            # Activar mouse look (botón derecho)
            self._mouse_look = True
            self._last_mouse = pygame.mouse.get_pos()
            pygame.mouse.set_visible(False)

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self._mouse_look = False
            pygame.mouse.set_visible(True)

        elif event.type == pygame.MOUSEMOTION and self._mouse_look:
            mx, my = pygame.mouse.get_pos()
            if self._last_mouse is not None:
                dx = mx - self._last_mouse[0]
                dy = my - self._last_mouse[1]
                self.yaw   += dx * CAM_MOUSE_SENS
                self.pitch  = max(
                    -CAM_PITCH_LIMIT,
                    min(CAM_PITCH_LIMIT, self.pitch - dy * CAM_MOUSE_SENS),
                )
            self._last_mouse = (mx, my)

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_h:
            self.reset()

    def reset(self) -> None:
        """Restaura la cámara a la posición y orientación con las que fue creada."""
        self.pos   = list(self._init_pos)
        self.yaw   = self._init_yaw
        self.pitch = self._init_pitch
        self.fov   = self._init_fov
        self._recompute_fov_scale()

    # ── Propiedades de solo lectura ───────────────────────────────────────────

    @property
    def forward(self) -> tuple[float, float, float]:
        """Vector unitario en la dirección de vista de la cámara."""
        yaw_r   = math.radians(self.yaw)
        pitch_r = math.radians(self.pitch)
        return (
            math.cos(yaw_r) * math.cos(pitch_r),
            math.sin(yaw_r) * math.cos(pitch_r),
            math.sin(pitch_r),
        )

    @property
    def right(self) -> tuple[float, float, float]:
        """Vector unitario hacia la derecha de la cámara (en el plano XY)."""
        yaw_r = math.radians(self.yaw)
        return (math.sin(yaw_r), -math.cos(yaw_r), 0.0)

    # ── Interno ───────────────────────────────────────────────────────────────

    def _recompute_fov_scale(self) -> None:
        """
        Calcula el factor de escala de perspectiva a partir del FOV actual.

        fov_scale = (altura_pantalla / 2) / tan(FOV / 2)

        Este factor multiplica las coordenadas de cámara normalizadas para
        obtener píxeles. A menor FOV (más zoom), mayor fov_scale.
        """
        self._fov_scale = (self.screen_h / 2.0) / math.tan(math.radians(self.fov / 2.0))

    def on_resize(self, screen_w: int, screen_h: int) -> None:
        """
        Actualiza las dimensiones de pantalla tras un resize de ventana o
        toggle de fullscreen. El fov_scale depende de screen_h, así que
        hay que recalcularlo — si no, la proyección queda desfasada del
        tamaño real de la superficie.
        """
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._recompute_fov_scale()


