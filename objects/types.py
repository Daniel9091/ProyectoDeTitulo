"""
En este archivo se encuentran los estados clave de los distintos objetos físicos de la simulación
"""

from enum import Enum

class ModularVehicleState(Enum):
    """
    Estados posibles que los VMs pueden tener
    """
    MOVING = "MOVING"                           # Viaja en el tren o en un track a velocidad normal
    ACCELERATING_UP = "ACCELERATING_UP"         # Subiendo por un arbol UP (desacelerando)
    ACCELERATING_DOWN = "ACCELERATING_DOWN"     # Bajando por un arbol DOWN (acelerando)

class PassengerState(Enum):
    """
    Estados posibles que los pasajeros pueden tener
    """
    WAITING_AT_ENTRANCE = "WAITING"                     # Recien spawneado, en la cola de la estacion
    MOVING_TO_LANE = "MOVING_TO_LANE"                   # Caminando hacia el anden
    WAITING_IN_LANE_QUEUE = "WAITING_IN_LANE_QUEUE"     # Llego al anden, esperando a que llegue un VM
    BOARDING = "BOARDING"                               # Esta subiendo al VM (progreso 0% - BOARDING_COMMIT_PROGRESS)
    IN_TRANSIT = "IN_TRANSIT"                           # Dentro de un VM, esta viajando
    ARRIVED = "ARRIVED"                                 # Llegado al destino, se elimina

class TreeDirection(Enum):
    """
    Dirección de un árbol de aceleración
    """
    UP = "UP"       # Árbol asciende (la gravedad lo hace desacelerar)
    DOWN = "DOWN"   # Árbol desciende (la gravedad lo hace acelerar)

class AndenState(Enum):
    """
    Estados posibles para los andenes en una estación.
    """
    ACTIVE = "ACTIVE"           # Anden activo habilitado para recibir VMs y Passengers
    INACTIVE = "INACTIVE"       # Anden inactivo incapacitado para recibir VMs o Passengers