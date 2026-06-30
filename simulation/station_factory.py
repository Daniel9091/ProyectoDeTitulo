"""
Fábrica de  estaciones con geometria 3D automatica.

Responsabilidades:
    - Recibir posicion 3D de la estación, largo de rampa y prfundidad de juntion
    - Calcular autoáticamente dónde van las junctiones en el belt (belt_x_up, belt_dn)
    - Garantizar que todos los árboles de la etacion tengan el mismo largo (ramp_length)
    - Instanciar AccelerationTree, BoardingLane, Junciton y Station

Lo que NO hace:
    - No registra en Network (responsabilidad de simulation_builder.py)
    - No conoce Brain ni ContinuousTrain
    - No maneja el wrap-around circular del belt (el builder hace belt_x % TOTAL_BELT_LENGTH)

Geometría (ejes: X = belt, Y = Ancho estacion, Z = Altura):

    Junction UP:    (belt_x_up,  station_origin.y, junction_depth)
    Juntion DOWN:   (belt_x_dn,  station_origin.y, junction_depth)

    Piso estación:  Z = dims.floor_height

    andén i:        extraction = (belt_x_up + dx_i, y_i, floor_height)
                    discharge  = (belt_x_dn - dx_i, y_i, floor_height)
    
    Para cada andén con offset y_i:
        dx_i = sqrt(ramp_length^2 - y_i^2 - dz^2)
        - anden externo (max|y_i|): dx menor -> lane mas larga
        - anden central (y_i = 0): dx mayor -> lane mas corta

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
from config.constants import TREE_ACCELERATION, MIN_VM_SEPARATION, TREE_LENGTH

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
    station_origin:             Vector3,                # Cordenadas del centro de la estacion
    junction_depth:             float,                  # Cordenada z de juntiones
    num_lanes:                  int,                    # Numero de andenes
    dims:                       StationDimensions,      # Dimensiones de la estacion ancho, largo altura
    passenger_rate:             float,                  # Tasa de produccion de pasajeros (s)
    destination_probabilities:  dict,                   # diccionario con probabilidades de que pasagero valla a estacion x
    vm_request_rate:            float,                  # Tasa de solicitudes de VMs (s)
    rng:                        random.Random,          # Generador de numeros aleatorios
    id_generator:               PassengerIdGenerator,   # Generador de IDs de pasajeros
    id_alloc:                   TrackIdAllocator,       # Generador de IDs de tracks        
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
        junciotn_down.belt_x puede exeder TOTAL_BELT_LENGTH si la estación está
        cerca del final del belt. El builder debe hacer:
            junction_down.belt_x %= TOTAL_BELT_LENGTH
        antes de registrar la junction y de pasar belt_x a ContinuousTrain.
    """

    # ── Geometría de accelerationTree ────────────────────────────────────────
    # Paso 1 — Offset Y máximo (andén más externo):
    y_offsets   = _lane_y_offsets(num_lanes, dims.y_length)
    y_ext       = max(abs(y) for y in y_offsets)                        # Offset del lane externo
    # Paso 2 - dz (componente Z del árbol)
    dz = dims.floor_height - junction_depth                             # Dif Zest - Zjun
    # Paso 3 — dx del árbol más externo
    dx_ext = math.sqrt(max(0.0, TREE_LENGTH**2 - y_ext**2 - dz**2))     # dx de lane externa
    #  posición X de junction
    x_left = station_origin.x - dims.x_length /2.0                      # borde X izq. de la lane externa
    x_right= station_origin.x + dims.x_length /2.0                      # borde X der. de la lane externa

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

        extraction = Vector3(x_ext, station_origin.y + y_i, dims.floor_height)
        discharge  = Vector3(x_dis, station_origin.y + y_i, dims.floor_height)

        up_trees.append(AccelerationTree(
            track_id            = up_id,                # ID
            start_pos           = j_up_3d,              # Coordenada de juntion up (origen)
            end_pos             = extraction,           # indica cordenada donde comienza la lane (termino)
            direction           = TreeDirection.UP,     # Indica arbol de subida
            base_acceleration   = TREE_ACCELERATION,    # aceleracion base del arbol
            min_vm_separation   = MIN_VM_SEPARATION,    # Minima separacion entre vm en el arbol (anti colicion)
            station_id          = None,                 # ID de la etacion a la que pertenece
        ))
        lanes.append(BoardingLane(
            track_id    = lane_id,      # ID
            start_pos   = extraction,   # Coordenada de inicio de lane
            end_pos     = discharge,    # Coordenada de fin de lane
        ))
        down_trees.append(AccelerationTree(
            track_id            = down_id,                # ID
            start_pos           = discharge,            # Coordenada de comienzo arbol (origen)
            end_pos             = j_down_3d,            # Indica cordenada de juntion down (termino)
            direction           = TreeDirection.DOWN,   # Indica arbol de bajada
            base_acceleration   = TREE_ACCELERATION,    # aceleracion base del arbol
            min_vm_separation   = MIN_VM_SEPARATION,    # Minima separacion entre vm en el arbol (anti colicion)
            station_id          = station_id,           # ID de la etacion a la que pertenece
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
    )

    return station, up_trees, lanes, down_trees, junction_up, junction_down

# ─── HELPERs ──────────────────────────────────────────────────────────────────

def _lane_y_offsets(num_lanes: int, y_length: float) -> list[float]:
    """
    Posiciones Y equidistantes, siempre siempre con lane central en Y=0
    
    Fórmula (y_ext = y_length / 2):
        n_right = ceil((num_lanes - 1) / 2)     <- lanes en Y positivo (=> n_left)
        n_left  = floor((num_lanes - 1) / 2)    <- lanes en Y negativo
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
    





#Preguntas:
#P9:
# Me referia a continuar con la nomesclatura de la simulacion a que continuemos escribiendo codigo en
# ingles y sin cambiarle los nombres a los objetos, por eso preferia acceleration tree en vez de rampa
# ahora veo que cometi un error por tratar de arreglar un typos que pusiste tu, pareciera que andenes
# no es lo mismo que lanes y sin querer les puse el mismo nombre pensando que eran lo mismo, quiero
# que corrijas el error que cometi pero con el nobre correcto en ingles de la clase original asi que 
# revisa los archivos responsables de este nombre, parece que el nombre original es andenes en station
# pero esta mal debe ser un nombre en ingles, dieme que podemos hacer para corregirlo#
# P8:
# por que cuando se crean los arboles de subida el id de la estacion es none y cuando se crean los 
# arboles de bajada se pone el id de la estacion#
# P7:
# no estoy entendiendo  como estas manerjando la geometria en las lineas 112 hacia abajo
# no entiendo la complicacion que tienes con el las cordenadas#
#
# P6:
# no entendi la primera parte de la geometria cuando haces los calculos, feliz que me la explques no se
# si estas siendo leal a lo que habiamos comberzado de que todas los arboles deben tener el mismo largo y
# mientras que las lanes se adaptan segun la hipotenusa que se forma con las distintas componentes en 
# (x,y,z)










# P5:
# esa funion que tienes puesta en el docstrig de la funion principal sea posible ponerla como funion real
# en el archivo y que pueda ser llamada con un un network para agregar los tracks que se acaban de poner?
# se podria hacer de maner automatica, es mas se podria pedir para crear la estacion para no tener que
# llamar a network ni niguna funcion despues o no?


# P4:
# me gustaria conservar la nomesclatura que tenemos hasta ahora asi que cambie el nombre de un par de
# atributos por que no quiero que sea confuso despues#

# P3:
# me gusto el treck id allocator pero no entiendo por que lo haces partir del numero 10, no debeir partir
# del numro 1?
# P2:
# el como se generan las lanes teine un oden espesifico que debe seguise que no es tan dificil de entender
# SIEMPRE va una lane en el cento con offest 0, siempre hay una al medio por lo tanto con una lane siempre
# va en el centro.
# par los casos impares se deben distribuir equiespaciadas todas las lanes por lo tanto queda la lane central
# y despues la mitad de las lanes que quedan se dejan al aldo del offset positivo y la otra mitad al offset 
# negativo, como deben qeudar equiespaciadas si tenemos el borde por ejemplo en y 10 el centro esta en 0 y el
# otro borde en -10 y tenemos 5 lanes, una lane queda en el cento dos lanes van a la derecha y dos lanes a la
# isquierda de la central, como como los bordes estan en 10 y el el cento esta en 0 dividimos el offset en
# 3 de tal manera que quda el central en 0, en 3,333 la siguiente lane, en 6,666 la siguiente y el borde quda
# en 10, hacia el otro lado sudede lo mismo una queda en -3,33 la siguiente en -6,666
# en el caso que sea par una va siempre en el centro y se entrega al lado derecho una mas al isquierdo y
# volvemos a ocupar el mismo metodo, si fueran 6 aneendes uno al centro 3 a la derecha 2 a la isquierda, en la
# derecha dividimos por 4, queda la central en 0 despues otra en 2,5 otra en 5 y la siguiente en 7,5 al lado
# isquierdo dividimos por 3 por que hay dos lanes que repartir y una queda en -3,33 y la siguiente en -6,66
# espero con esto haber clarificado el rodden de los andenes# 
# 
# # P1:
# para responder a lo del mapa de calor se forma un triangulo entre juntion y el comienzo de las lanes
# la hipotenusa de este triangulo es la rampa o arbol, que tiene componentes en x y en z siempre
# en los arboels up sube desde el tren continuo hasta la estacion (eje z) ademas en el eje x avanza
# varios metros ej 350 metros, para la lane central el despasamiento en y es 0 pero para el resto de las
# lanes que la acompañan hay un deplasamiento en z del offest que tenga la segunda lane con respecto a la 
# lane central.
# como tenemos un largo de el arbol de acceleracion definido la correcta manera de calcular la hipotenusa es
# con todas las componentes vale decir las coponentes de jutnion menos las coponentes de la lane con mas offest
# al cuadrado y eso dara la hipotenusa.
# como bien se dijo este calculo es para calcular la posicon en x de juncion, por que la z ya sabemos que es
# la profundidad dada y el y es la del origen de la estaicon (la estacion esta justo arriba) pero el x hay
# que definirlo por que si tenemos estaciones con mas andenes podramos tener offest mas grandes por lo tanto
# se moveria un pelo la juntion
# ahora una vez que se calcula la posion del belt con la lane con mas offest y como ya tenemos el largo definido
# corresponde calcular el inicio de las lanes que tienen menos offest (partiran las lanes un poco despues
# por que deben compensar el no tener tanto componente y (menor offset) de esta manera las lanes mas centrales
# partiran un poco mas al interior de la estacion), esto mismo paras para las junciton de down
# espero haber acalarado ese 30 %



