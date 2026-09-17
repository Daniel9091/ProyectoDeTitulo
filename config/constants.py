"""
Constantes globales de NSim agrupadas por subsistema: física, boarding,
tren continuo, árboles de aceleración, predicción de colisiones, visualización,
cámara, dimensiones de VM y estación, y telemetría.

Las constantes derivadas (TRAIN_SPACING, TREE_DZ, MIN_VM_SEPARATION) se calculan
automáticamente al cargar el módulo a partir de las primitivas anteriores.
"""
# CTE. FÍSICAS

GRAVITY = 9.8           # aceleración de gravedad (m/s²)
ACCEL_RANGE_MIN = 0.2   # aceleración mínima permitida en ajuste de colisión (m/s²)
ACCEL_RANGE_MAX = 1.5   # aceleración máxima permitida en ajuste de colisión (m/s²)

# CTE. BOARDING PASAJEROS

BOARDING_LANE_SPEED = 2.0       # velocidad del VM en el boarding lane (m/s)
BOARDING_COMMIT_PROGRESS = 0.5  # progreso al que se completa el abordaje (%)
PASSENGER_WALK_SPEED = 0.5      # velocidad peatonal (m/s)

# CTE. TREN CONTINUO

TRAIN_SPEED = 20.0      # velocidad constante del tren continuo (m/s)
TRAIN_VM_LENGTH = 1.0   # largo de cada VM en el belt (m)
TRAIN_GAP = 1.0         # espacio entre cada VM en el belt (m)

TRAIN_SPACING = TRAIN_VM_LENGTH + TRAIN_GAP                             # distancia entre centros de VMs (m)
TREE_DZ = (TRAIN_SPEED**2 - BOARDING_LANE_SPEED**2) / (2 * GRAVITY)     # diferencia en z de belt con la estación

# CTE. ÁRBOLES DE ACELERACIÓN

MIN_VM_SEPARATION = TRAIN_SPACING           # separación mínima entre centros de VMs en la cima del árbol UP (m)
TREE_LENGTH = 400                           # largo de los árboles de aceleración (m)

# CTE. PREDICCIÓN DE COLISIONES


SLOT_SEARCH_RANGE_RESERVATION = 40   # ±20 slots — reservas necesitan mucho margen
SLOT_SEARCH_RANGE_DEMAND      = 10   # 10 slots atrás

BURST_WINDOW_SAFETY_MARGIN = 0  # cuántos slots de más va a tener la ventana para prevenir saturación

# CTE. VISUALIZACIÓN

FPS = 30                # frames por segundo
SCREEN_WIDTH = 1200     # ancho de la pantalla (px)
SCREEN_HEIGHT = 800     # alto de la pantalla (px)

# CTE. CÁMARA

CAM_FOV_DEFAULT    = 60.0   # campo de visión por defecto (grados)
CAM_FOV_MIN        = 15.0   # zoom máximo alcanzable (FOV mínimo)
CAM_FOV_MAX        = 100.0  # zoom mínimo alcanzable (FOV máximo)
CAM_NEAR_CLIP      = 0.5    # plano de recorte cercano — puntos más cerca no se renderizan (m)
CAM_MOVE_SPEED     = 200.0  # velocidad de traslación con teclado (m/s)
CAM_ROT_SPEED      = 60.0   # velocidad de rotación con teclado (°/s)
CAM_MOUSE_SENS     = 0.25   # sensibilidad de mouse look (°/pixel)
CAM_ZOOM_KEY_SPEED = 5.0    # velocidad de zoom con teclas Z/X (°/s)
CAM_PITCH_LIMIT    = 89.0   # límite superior/inferior de pitch para evitar gimbal lock (°)

# CTE. DIMENSIONES VM

VM_RENDER_WIDTH  = TRAIN_VM_LENGTH      # ancho del VM en 3D (m)
VM_RENDER_DEPTH  = 1.0                  # profundidad del VM en 3D (m)
VM_RENDER_HEIGHT = 1.5                  # alto del VM en 3D (m)

# CTE. DIMENSIONES ESTACIONES

STATION_X_LENGTH        = 100.0         # largo de la estación  dx  (m)
STATION_Y_LENGTH        = 30.0          # ancho de la estación  dy  (m)
STATION_FLOOR_HEIGHT    = 5.0           # altura de los pisos   dz  (m)
STATION_NUM_FLOORS      = 1             # cantidad de pisos

# CTE. LOGS

TELEMETRY_ENABLED:  bool    = False   # True: guarda logs, False no guarda logs
SNAPSHOT_INTERVAL:  float   = 60.0      # segundos entre station_snapshot events (s)
