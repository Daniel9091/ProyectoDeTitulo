"""
Este archivo contiene todas las constantes utilizadas en la simulacion
Note que muchas variables dependen de otras asi que podria ser buena idea realizar calculos en base a CTEs.
"""
# CTE. TREN CONTINUO

TRAIN_SPEED = 20.0      # velocidad constante del tren continuo (m/s)
TRAIN_VM_LENGTH = 1.0   # largo de cada VM en el belt (m)
TRAIN_GAP = 1.0         # espacio entre cada VM en el belt (m)

TRAIN_SPACING = TRAIN_VM_LENGTH + TRAIN_GAP    # distancia entre centros de VMs (m)

# CTE. FISICAS

GRAVITY = 9.8           # aceleracion de grabedad (m/s²)
ACCEL_RANGE_MIN = 0.2   # aceleracion minima permitida en ajuste de colicion (m/s²)
ACCEL_RANGE_MAX = 1.5   # aceleracion maxima permitida en ajuste de colicion (m/s²)

# CTE. BOARDING PASAGEROS

BOARDING_LANE_SPEED = 2.0       # velocidad del VM en el boarding lane (m/s)
BOARDING_COMMIT_PROGRESS = 0.5  # progreso al que se completa el abordaje (%)
PASSENGER_WALK_SPEED = 0.5      # velocidad peatonal (m/s)

# CTE. ARBOLES DE ACELERACION

MIN_VM_SEPARATION = TRAIN_SPACING           # sepaparación mínima entre centros de VMs en la cima del árbol UP (m)
TREE_LENGTH = 400                           # Largo de los arboles de aceleracion (m)


# CTE. PREDICCION DE COLICIONES

SLOT_SEARCH_RANGE = 10          # rango de busqueda bidireccional de slots

# CTE. VISUALISACION

FPS = 30                # frames por segundo
SCREEN_WIDTH = 1200     # ancho de la pantalla (px)
SCREEN_HEIGHT = 800     # alto de la pantalla (px)

