"""
Vehículo modular (VM) - Unidad básica de transporte en NSim.

Responsabilidades de este archivo:
Modelar el estado INTERNO de un VM: quién es, qué es, qué capacidad tiene,
quién lleva a bordo, a dónde va, y dónde está en el espacio 3D

Lo que NO hace este archivo:
    - No calcula rutas              
    - No mueve el VM                
    - No detecta colisiones         
    - No gestiona asignaciones      
    - No lleva penalizaciones       
"""

from objects.math3d import Vector3
from objects.types import ModularVehicleState
from objects.passenger import Passenger

class ModularVehicle:
    """
    Representa un Vehículo Modular (VM).

    El VM no se mueve a sí mismo. Su posición y slot son ESCRITOS por el
    sistema de movimiento externo (ContinuousTrain o AccelerationTree)
    cada frame. El VM solo conoce su propio estado interno.
    """

    def __init__(self, vehicle_id: int, capacity: int):
        # IDENTIDAD
        self.vehicle_id = vehicle_id
        self.capacity = capacity

        # ESTADO DE MOVIMIENTO
        self.state: ModularVehicleState = ModularVehicleState.MOVING

        # POSICION
        # expone su posición pero no la calcula
        self.position: Vector3 = Vector3()

        # SLOT EN TREN CONTINUO
        # None se ocupa cuando esta fuera del tren continuo
        self.slot_index: int | None = None

        # PASAJEROS ABORDO
        self.passengers_on_board: list[Passenger] = []

        # NAVEGACION
        # None se ocupa cuando no tiene destino fijo
        self.destination_station_id: int | None = None
        # None mientras el vm no tenga un arbol de bajada reservado
        self.reserved_tree_acceleration: float | None = None

        # METRICAS INTERNAS
        self.operational_time: float = 0.0
        self.total_distance_traveled: float = 0.0
        self.distance_carrying_passengers: float = 0.0

    # PROPIEDADES DE ESTADO
    @property
    def passenger_count(self) -> int:
        """
        Cantidad de pasajeros actualmente abordo
        """
        return len(self.passengers_on_board)

    @property
    def is_full(self) -> bool:
        """
        True si el VM está lleno
        Se puede ocupar para saber si se pueden agregar más pasajeros
        """
        return self.passenger_count >= self.capacity
    
    @property
    def has_destination(self) -> bool:
        """
        True si el VM tiene un destino fijado
        """
        return self.destination_station_id is not None
    
    # GESTION DE PASAJEROS
    def board(self, passenger) -> bool:
        """
        Embarca pasajeros en el VM
        Retorna True si se pudo embarcar
        Retorna False sin modificar el estado si el VM está lleno
        """
        if self.is_full:
            return False
        
        self.passengers_on_board.append(passenger)
        return True

    def disembark(self, station_id: int) -> list[Passenger]:
        """
        Retira del VM a todos los pasajeros cuyo destino sea station_id.

        Retorna la lista de pasajeros que bajaron (puede ser vacía).
        Llamado por el sistema de estaciones cuando un VM pasa por una estación.

        Diseño: en lugar de que el Passenger se desembarque a si mismo,
        el VM decide quién baja según el destino.

        """
        staying = []
        leaving = []
        for passenger in self.passengers_on_board:
            if passenger.destination_station_id == station_id:
                leaving.append(passenger)
            else:
                staying.append(passenger)
        self.passengers_on_board = staying
        return leaving

    def disembark_all(self) -> list[Passenger]:
        """
        Retira TODOS los pasajeros del VM sin distinción de destino.
        Usado cuando el VM entra a una estación aunque no sea el destino de todos.
        """
        departed = list(self.passengers_on_board)
        self.passengers_on_board = []
        return departed

    # GESTION DE DESTINO
    def assign_destination(self, station_id: int) -> None:
        """
        Asigna un destino al VM
        """
        self.destination_station_id = station_id

    def clear_destination(self) -> None:
        """
        Limpia el destino actual del VM
        """
        self.destination_station_id = None
    
    # CICLO DE SIMULACION
    def update(self,dt:float) -> None:
        """
        Actualiza metricas internas

        IMPORTANTE: Este metodo NO mueve el VM. La posicion es responsabilidad
        de otros objetos, en este metodo solo se actualizan los tiempos operativos
        """
        self.operational_time += dt
    
    # DEBUG
    def __repr__(self) -> str:
        return (
        f"Vehicle(id={self.vehicle_id}, "
        f"state={self.state.value}, "
        f"pax={self.passenger_count}/{self.capacity}, "
        f"dest={self.destination_station_id})"
    )        
