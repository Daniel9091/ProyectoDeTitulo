"""
En este archvio se ecuentran los estados claves de los distintos objetos fisicos de la simulacion
"""

from enum import Enum

class ModularVehicleState(Enum):
    """
    Estados posibles que los Vms pueden tener 
    """
    MOVING = "MOVING"                           # Viaja en el tren o en un track a velocidad normal
    ACCELERATING_UP = "ACCELERATING_UP"         # Subiendo por un arbol UP (desaselerando)
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
    Estados posibles que los arboles de aceleracion pueden tener
    """
    UP = "UP"       # Arbol aciende, (la grabedad lo hace desaselerar)
    DOWN = "DOWN"   # Arbol deciende, (la grabedad lo hace acelerar)

class CollisionAction(Enum):
    """
    Estados posibles de la predicion de colisiones
    """
    FREE = "FREE"               # Hay slot disponible, sin problema
    CONSUME = "CONSUME"         # No hay slot disponible pero hay un VM que puede ser consumido para liberar espacio
    INEVITABLE = "INEVITABLE"   # No hay solucion posible, colicion inevitable


