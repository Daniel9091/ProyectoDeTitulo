"""
Fábrica de estaciones con geometría 3D automática.

Responsabilidades:
    - Recibir posición 3D de la estación, largo de rampa y profundidad de junction
    - Calcular automáticamente dónde van las junctions en el belt (belt_x_up, belt_dn)
    - Garantizar que todos los árboles de la estación tengan el mismo largo (ramp_length)
    - Instanciar AccelerationTree, BoardingLane, Junction y Station

Lo que NO hace:
    - No registra en Network (responsabilidad de simulation_builder.py)
    - No conoce Brain ni ContinuousTrain
    - No maneja el wrap-around circular del belt (el builder hace belt_x % TOTAL_BELT_LENGTH)

Geometría (ejes: X = belt, Y = Ancho estacion, Z = Altura):

    Junction UP:    (belt_x_up,  station_origin.y, junction_depth)
    Junction DOWN:  (belt_x_dn,  station_origin.y, junction_depth)

    Piso estación:  Z = dims.floor_height

    andén i:        extraction = (belt_x_up + dx_i, y_i, floor_height)
                    discharge  = (belt_x_dn - dx_i, y_i, floor_height)
    
    Para cada andén con offset y_i:
        dx_i = sqrt(ramp_length^2 - y_i^2 - dz^2)
        - andén externo (max|y_i|): dx menor → lane más larga
        - andén central (y_i = 0): dx mayor → lane más corta

    Posiciones Y (siempre lane central en Y=0; soporta N par e impar):
        N=1 → [0]
        N=2 → [0,                                     +y_length/4]
        N=3 → [-y_length/4,           0,              +y_length/4]
        N=4 → [-y_length/4,  0,       +y_length/6,   +y_length/3]
        N=5 → [-y_length/3, -y_length/6, 0, +y_length/6, +y_length/3]      
        Ver _lane_y_offsets() para la fórmula general
"""

import math
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from objects.math3d import Vector3
from objects.types import TreeDirection
from objects.station import Station, StationDimensions
from objects.passenger_id_generator import PassengerIdGenerator
from tracks.acceleration_tree import AccelerationTree
from tracks.boarding_lane import BoardingLane
from tracks.junction import Junction
from config.constants import MIN_VM_SEPARATION, TREE_LENGTH, TREE_DZ, STATION_X_LENGTH, STATION_Y_LENGTH, STATION_FLOOR_HEIGHT, STATION_NUM_FLOORS



# ─── ALLOCADOR DE IDs ────────────────────────────────────────────────────────

class TrackIdAllocator:
    """
    Genera IDs únicos para tracks y junctions en toda la red.
    Crear UNA instancia en simulation_builder y pasarla a cada create_station.
    """
    def __init__(self, start: int = 1):
        self._next = start
    
    def next(self) -> int:
        val = self._next
        self._next += 1
        return val

# ─── FUNCIÓN PRINCIPAL ───────────────────────────────────────────────────────
def create_station(
    station_id:                 int,                    # ID
    station_origin:             Vector3,                # Coordenadas del centro de la estación
    num_lanes:                  int,                    # Numero de andenes
    passenger_rate:             float,                  # Tasa de produccion de pasajeros (s)
    destination_probabilities:  dict,                   # Probabilidades de destino por estación
    vm_request_rate:            float,                  # Tasa de solicitudes de VMs (s)
    rng:                        random.Random,          # Generador de numeros aleatorios
    id_generator:               PassengerIdGenerator,   # Generador de IDs de pasajeros
    id_alloc:                   TrackIdAllocator,       # Generador de IDs de tracks
    recorder,      
) -> tuple[Station, list, list, list, Junction, Junction]:
    """
    Construye estación completa con geometría 3D calculada automáticamente.

    Retorna:
        station, up_trees, lanes, dn_trees, junction_up, junction_down

        up_trees:       list[AccelerationTree]    - uno por andén
        lanes:          list[BoardingLane]        - uno por andén
        dn_trees:       list[AccelerationTree]    - uno por andén
        junction_up:    Junction                  - agrupa todos los up_trees
        junction_down:  Junction                  - agrupa todos los down_trees

    ADVERTENCIA: belt circular:
        junction_down.belt_x puede exceder TOTAL_BELT_LENGTH si la estación está
        cerca del final del belt. El builder debe hacer:
            junction_down.belt_x %= TOTAL_BELT_LENGTH
        antes de registrar la junction y de pasar belt_x a ContinuousTrain.
    """

    # ── Geometría de accelerationTree ────────────────────────────────────────
    # Paso 1 — Offset Y máximo (andén más externo):
    y_offsets   = _lane_y_offsets(num_lanes, STATION_Y_LENGTH)
    y_ext       = max(abs(y) for y in y_offsets)                        # Offset del lane externo
    # Paso 2 - dz (componente Z del árbol)
    dz = TREE_DZ
    junction_depth = station_origin.z - TREE_DZ                         # profundidad del belt
    # Paso 3 — dx del árbol más externo
    dx_ext = math.sqrt(max(0.0, TREE_LENGTH**2 - y_ext**2 - dz**2))     # dx de lane externa
    #  posición X de junction
    x_left = station_origin.x - STATION_X_LENGTH /2.0                      # borde X izq. de la lane externa
    x_right= station_origin.x + STATION_X_LENGTH /2.0                      # borde X der. de la lane externa

    belt_x_up   = x_left    - dx_ext                                    # junction UP (coordenada X lineal)
    belt_x_down = x_right   + dx_ext                                    # junction DOWN (coordenada X lineal)
    # Vector3 Junction UP y DOWN
    j_up_3d     = Vector3(belt_x_up, station_origin.y, junction_depth)
    j_down_3d   = Vector3(belt_x_down, station_origin.y, junction_depth)

    # ── Construcción por andén ─────────────────────────────────────────────
    up_trees:   list = []
    lanes:      list = []
    down_trees: list = []
    platforms:  list = []

    for y_i in y_offsets:
        dx_i = math.sqrt(max(0.0, TREE_LENGTH**2 - y_i**2 - dz**2))     # Se calcula componente x de la lane
        x_ext = belt_x_up + dx_i                                        # se suma o se resta este componente x al origen (juntion)
        x_dis = belt_x_down - dx_i

        up_id       = id_alloc.next()
        lane_id     = id_alloc.next()
        down_id     = id_alloc.next()

        extraction = Vector3(x_ext, station_origin.y + y_i, station_origin.z)
        discharge  = Vector3(x_dis, station_origin.y + y_i, station_origin.z)

        up_trees.append(AccelerationTree(
            track_id            = up_id,                # ID
            start_pos           = j_up_3d,              # Coordenada de juntion up (origen)
            end_pos             = extraction,           # Coordenada de extracción: terminus del árbol UP, origen de la lane
            direction           = TreeDirection.UP,     # Indica arbol de subida
            min_vm_separation   = MIN_VM_SEPARATION,    # Minima separacion entre vm en el arbol (anti colicion)
            station_id          = None,                 # ID de la estación a la que pertenece
            recorder            = recorder   
        ))
        lanes.append(BoardingLane(
            track_id    = lane_id,      # ID
            start_pos   = extraction,   # Coordenada de inicio de lane
            end_pos     = discharge,    # Coordenada de fin de lane
            recorder    = recorder
        ))
        down_trees.append(AccelerationTree(
            track_id            = down_id,                # ID
            start_pos           = discharge,            # Coordenada de comienzo del árbol (origen)
            end_pos             = j_down_3d,            # Coordenada de junction DOWN (término)
            direction           = TreeDirection.DOWN,   # Indica arbol de bajada
            min_vm_separation   = MIN_VM_SEPARATION,    # Minima separacion entre vm en el arbol (anti colicion)
            station_id          = station_id,           # ID de la estación a la que pertenece
            recorder            = recorder
        ))
        platforms.append({
            'lane'            : lanes[-1],
            'up_tree_id'      : up_id,
            'down_tree_id'    : down_id,
            'extraction_point': extraction,
            'discharge_point' : discharge,
        })
    
    # ── Junctions ──────────────────────────────────────────────────────────
    j_up_id     = id_alloc.next()
    j_down_id   = id_alloc.next()
    junction_up = Junction(j_up_id, belt_x_up, station_id, TreeDirection.UP, up_trees)
    junction_down = Junction(j_down_id, belt_x_down, station_id, TreeDirection.DOWN, down_trees)

    # ── Station ────────────────────────────────────────────────────────────

    dims = StationDimensions(
        x_length        = STATION_X_LENGTH,   
        y_length        = STATION_Y_LENGTH,    
        floor_height    = STATION_FLOOR_HEIGHT,   
        num_floors      = STATION_NUM_FLOORS,
    )

    station = Station(
        station_id                  = station_id,
        origin                      = station_origin,
        dimensions                  = dims,
        passenger_rate              = passenger_rate,
        destination_probabilities   = destination_probabilities,
        vm_request_rate             = vm_request_rate,
        platforms                   = platforms,
        rng                         = rng,
        id_generator                = id_generator,
        recorder                    = recorder,
    )

    return station, up_trees, lanes, down_trees, junction_up, junction_down

# ─── HELPERs ──────────────────────────────────────────────────────────────────

def _lane_y_offsets(num_lanes: int, y_length: float) -> list[float]:
    """
    Posiciones Y equidistantes, siempre con lane central en Y=0
    
    Fórmula (y_ext = y_length / 2):
        n_right = ceil((num_lanes - 1) / 2)     <- lanes en Y positivo (derecha)
        n_left  = floor((num_lanes - 1) / 2)    <- lanes en Y negativo (izquierda)
        step_right = y_ext / (n_right + 1)
        step_left  = y_ext / (n_left + 1)

    Las lanes no llegan al borde físico (y_ext) - siempre queda un espacio.

    Ejemplos con y_length = 20 (y_ext = 10):
        N=1 → [0]
        N=2 → [0,  +5.0]
        N=3 → [-5.0,  0,  +5.0]
        N=4 → [-5.0,  0,  +3.33,  +6.67]
        N=5 → [-6.67,  -3.33,  0,  +3.33,  +6.67]
        N=6 → [-6.67,  -3.33,  0,  +2.5,  +5.0,  +7.5]
    """
    if num_lanes <=0:
        raise ValueError(f"num_lanes debe ser > 0, recibido {num_lanes}")
    if num_lanes == 1:
        return[0.0]
    
    y_ext = y_length / 2.0
    n_right = math.ceil((num_lanes -1) / 2)
    n_left  = math.floor((num_lanes -1) / 2)

    step_right = y_ext / (n_right + 1)
    step_left  = y_ext / (n_left + 1) if n_left >0 else 0.0

    right = [+i * step_right for i in range(1, n_right +1)]
    left =  [-i * step_left for i in range(1, n_left +1)]

    return sorted(left + [0.0] + right)

def connect_station_to_network(
        network,
        up_trees:           list,
        lanes:              list,
        down_trees:         list,
        junction_up:        Junction,
        junction_down:      Junction,
) -> None:
    """
    Registra en Network los tracks y junctions de una estación.

    Uso típico en el builder:
        station, *rest = create_station(...)
        connect_station_to_network(network, *rest)
    """
    for track in (up_trees + lanes + down_trees):
        network.add_track(track)
    for up, lane, down in zip(up_trees, lanes, down_trees):
        network.connect(up.track_id, lane.track_id)
        network.connect(lane.track_id, down.track_id)
    network.add_junction(junction_up)
    network.add_junction(junction_down)
    