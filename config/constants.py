"""
Este archivo contiene todas las constantes utilizadas en la simulacion
Note que muchas variables dependen de otras asi que podria ser buena idea realizar calculos en base a CTEs.
"""
# CTE. FISICAS

GRAVITY = 9.8           # aceleracion de grabedad (m/s²)
ACCEL_RANGE_MIN = 0.2   # aceleracion minima permitida en ajuste de colicion (m/s²)
ACCEL_RANGE_MAX = 1.5   # aceleracion maxima permitida en ajuste de colicion (m/s²)

# CTE. BOARDING PASAGEROS

BOARDING_LANE_SPEED = 2.0       # velocidad del VM en el boarding lane (m/s)
BOARDING_COMMIT_PROGRESS = 0.5  # progreso al que se completa el abordaje (%)
PASSENGER_WALK_SPEED = 0.5      # velocidad peatonal (m/s)

# CTE. TREN CONTINUO

TRAIN_SPEED = 20.0      # velocidad constante del tren continuo (m/s)
TRAIN_VM_LENGTH = 1.0   # largo de cada VM en el belt (m)
TRAIN_GAP = 1.0         # espacio entre cada VM en el belt (m)

TRAIN_SPACING = TRAIN_VM_LENGTH + TRAIN_GAP                             # distancia entre centros de VMs (m)
TREE_DZ = (TRAIN_SPEED**2 - BOARDING_LANE_SPEED**2) / (2 * GRAVITY)     # diferencia en z de belt con la estacion

# CTE. ARBOLES DE ACELERACION

MIN_VM_SEPARATION = TRAIN_SPACING           # sepaparación mínima entre centros de VMs en la cima del árbol UP (m)
TREE_LENGTH = 400                           # Largo de los arboles de aceleracion (m)

# CTE. PREDICCION DE COLICIONES

SLOT_SEARCH_RANGE = 10          # rango de busqueda bidireccional de slots 

# CTE. VISUALISACION

FPS = 30                # frames por segundo
SCREEN_WIDTH = 1200     # ancho de la pantalla (px)
SCREEN_HEIGHT = 800     # alto de la pantalla (px)

# CTE. CAMARA

CAM_FOV_DEFAULT    = 60.0   # campo de visión por defecto (grados)
CAM_FOV_MIN        = 15.0   # zoom máximo alcanzable (FOV mínimo)
CAM_FOV_MAX        = 100.0  # zoom mínimo alcanzable (FOV máximo)
CAM_NEAR_CLIP      = 0.5    # plano de recorte cercano — puntos más cerca no se renderizan (m)
CAM_MOVE_SPEED     = 200.0  # velocidad de traslación con teclado (m/s)
CAM_ROT_SPEED      = 60.0   # velocidad de rotación con teclado (°/s)
CAM_MOUSE_SENS     = 0.25   # sensibilidad de mouse look (°/pixel)
CAM_ZOOM_KEY_SPEED = 5.0    # velocidad de zoom con teclas Z/X (°/s)
CAM_PITCH_LIMIT    = 89.0   # límite superior/inferior de pitch para evitar gimbal lock (°)

# CTE. DIMENCIONES VM

VM_RENDER_WIDTH  = TRAIN_VM_LENGTH      # ancho del VM en 3D (m)
VM_RENDER_DEPTH  = 1.0                  # profundidad del VM en 3D (m)
VM_RENDER_HEIGHT = 1.5                  # alto del VM en 3D (m)

# CTE. DIMENCIONES ESTACIONES

STATION_X_LENGTH        = 100.0         # largo de la estacion  dx  (m)
STATION_Y_LENGTH        = 30.0          # ancho de la estacion  dy  (m)
STATION_FLOOR_HEIGHT    = 5.0           # altura de los pisos   dz  (m)
STATION_NUM_FLOORS      = 1             # Canitdad de pisos
