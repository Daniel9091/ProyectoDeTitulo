"""
Pasajero (Passenger) — Entidad a ser transportada en NSim.

Responsabilidad de este archivo:
    Modelar el estado INTERNO de un pasajero: identidad, origen, destino,
    estado del viaje, y las dos métricas clave (spawn_time, arrival_time).

Diseño deliberado — lo que NO tiene este archivo:
    - Sin posición 3D:
        El pasajero se mueve siempre DENTRO de una estación (centro → inicio de lane).
        La Estación tiene esas coordenadas mapeadas; el Passenger no las necesita.
    - Sin timestamps intermedios (boarding_start, boarding_complete, etc.):
        Solo nos interesan cuándo nació y cuándo llegó.
        Tiempo de viaje = arrival_time - spawn_time.
    - No se embarca solo:
        Es el VM quien llama board(). El Passenger solo registra que está a bordo.
    - No calcula rutas ni interactúa con tracks.
"""

from objects.types import PassengerState
from objects.math3d import Vector3

class Passenger:
    """
    Representa un Pasajero.

    Ciclo de vida:
        WAITING_AT_ENTRANCE   (spawneado en la estación, esperando que lo asignen)
            ↓ La Estación le asigna una lane
        MOVING_TO_LANE        (caminando del centro de la estación al inicio de la lane)
            ↓ Llega al inicio de la lane
        WAITING_IN_LANE_QUEUE (en cola, esperando que llegue un VM)
            ↓ Un VM llega y comienza el proceso de embarque
        BOARDING              (subiendo al VM, en progreso)
            ↓ Embarque completo (BOARDING_COMMIT_PROGRESS alcanzado)
        IN_TRANSIT            (viajando dentro del VM)
            ↓ VM llega a estación destino
        ARRIVED               (llegó, se elimina de la simulación)
    """

    def __init__(self, passenger_id: int, origin_station_id: int, destination_station_id: int, spawn_time: float):
        # IDENTIDAD
        self.passenger_id = passenger_id
        self.origin_station_id = origin_station_id
        self.destination_station_id = destination_station_id
        # STATE
        self.state = PassengerState.WAITING_AT_ENTRANCE
        # METRICAS
        self.spawn_time = spawn_time
        self.arrival_time: float | None = None
        # REFERENCIA VM
        self.vehicle_id = None
        
    @property
    def is_arrived(self) -> bool:
        """
        True si el pasajero llegó a su destino
        """
        return self.state == PassengerState.ARRIVED
    
    @property
    def is_in_transit(self)-> bool:
        """
        True si el pasagero esta en transito
        """
        return self.state == PassengerState.IN_TRANSIT
    
    @property
    def is_waiting(self) -> bool:
        """
        True si el pasajero inmovil esperando (en la estacion o en la cola de lane)
        """
        return self.state in(
            PassengerState.WAITING_AT_ENTRANCE,
            PassengerState.WAITING_IN_LANE_QUEUE,
        )

    # TRANSISIONES DE ESTADO
    # Cada transicion valida que el estado previo sea correcto.

    def start_moving_to_lane(self) -> None:
        """
        WATING_AT_ENTRANCE -> MOVING_TO_LANE
        """
        if self.state != PassengerState.WAITING_AT_ENTRANCE:
            raise ValueError(
                f"Passenger {self.passenger_id}:"
                f"no puede ir a MOVING_TO LANE desde {self.state.value}"
            )
        self.state = PassengerState.MOVING_TO_LANE
    
    def arrive_at_lane(self)-> None:
        """
        MOVING_TO_LANE -> WAITING_IN_LANE_QUEUE
        """
        if self.state != PassengerState.MOVING_TO_LANE:
            raise ValueError(
                f"Passenger {self.passenger_id}:"
                f"no puede ir a WAITING_IN_LANE_QUEUE desde {self.state.value}"
            )
        self.state = PassengerState.WAITING_IN_LANE_QUEUE

    def start_boarding(self)-> None:
        """
        WAITING_IN_LANE_QUEUE -> BOARDING
        """
        if self.state != PassengerState.WAITING_IN_LANE_QUEUE:
            raise ValueError(
                f"Passenger {self.passenger_id}:"
                f"no puede ir a BOARDING desde {self.state.value}"
            )
        self.state = PassengerState.BOARDING

    def complete_boarding(self, vehicle_id: int)-> None:
        """
        BOARDING -> IN_TRANSIT
        Registra en que VM viaja (por id no por referencia)
        """
        if self.state != PassengerState.BOARDING:
            raise ValueError(
                f"Passenger {self.passenger_id}:"
                f"no puede ir a IN_TRANSIT desde {self.state.value}"
            )
        self.state = PassengerState.IN_TRANSIT
        self.vehicle_id = vehicle_id

    def arrive(self, current_time: float) -> None:
        """
        IN_TRANSIT -> ARRIVED
        Registra el tiempo de llegada para calcular metrica del viaje
        """
        if self.state != PassengerState.IN_TRANSIT:
            raise ValueError(
                f"Passenger {self.passenger_id}:"
                f"no puede ir a ARRIVED desde {self.state.value}"
            )
        self.state = PassengerState.ARRIVED
        self.arrival_time = current_time
        self.vehicle_id = None              # Ya no esta en un VM

    # METRICAS

    def total_travel_time(self) -> float:
        """
        Tiempo total desde spawn hasta llegada
        Retorna None si el pasagero no ha llegado.
        """
        if self.arrival_time is None:
            return None
        return self.arrival_time - self.spawn_time

    # DEBUG

    def __repr__(self) -> str:
        return (
            f"Passenger(id={self.passenger_id}, "
            f"{self.origin_station_id}→{self.destination_station_id}, "
            f"state={self.state.value})"
        )









