from typing import TYPE_CHECKING, Dict, Any
from objects.base import Vector3

# Para evitar importaciones circulares, usamos TYPE_CHECKING para las anotaciones de tipo
if TYPE_CHECKING:
    from objects.stations import Station
    from objects.boarding_lane import BoardingLane
    from objects.modular_vehicles import ModularVehicle

# Definición de los estados del pasajero
WAITING_AT_ENTRANCE = "WAITING_AT_ENTRANCE"
MOVING_TO_LANE = "MOVING_TO_LANE"
WAITING_IN_LANE_QUEUE = "WAITING_IN_LANE_QUEUE"
BOARDING = "BOARDING"
IN_TRANSIT = "IN_TRANSIT"
ARRIVED = "ARRIVED"

class Passenger:
    """
    Representa un pasajero individual en la simulación, actuando como una máquina de estados.
    Gestiona el movimiento a pie del pasajero dentro de una estación y su estado
    durante el proceso de embarque y tránsito.
    """

    def __init__(self, passenger_id: str, origin_station_id: str, destination_station_id: str, initial_position: Vector3):
        """
        Inicializa una nueva instancia de Passenger.

        Args:
            passenger_id (str): Identificador único del pasajero.
            origin_station_id (str): ID de la estación de origen del pasajero.
            destination_station_id (str): ID de la estación de destino del pasajero.
            initial_position (Vector3): Posición inicial del pasajero en el mundo 3D.
        """
        self.passenger_id: str = passenger_id
        self.origin_station_id: str = origin_station_id
        self.destination_station_id: str = destination_station_id

        self.current_position: Vector3 = initial_position  # Posición actual del pasajero
        self.target_position: Vector3 = initial_position    # Posición objetivo a la que se dirige el pasajero

        self.state: str = WAITING_AT_ENTRANCE               # Estado actual del pasajero (inicial)
        self.walk_speed: float = 0.5                        # Velocidad de movimiento a pie (m/s)

        self.current_station: 'Station' = None              # Referencia a la estación donde se encuentra el pasajero
        self.current_lane: 'BoardingLane' = None            # Referencia al andén de embarque asignado
        self.assigned_vehicle: 'ModularVehicle' = None      # Referencia al VM asignado para el embarque/tránsito

    def update(self, dt: float):
        """
        Actualiza el estado del pasajero, principalmente para el movimiento a pie (a 0.5 m/s).
        """
        
        # --- Estado: Moviéndose a pie hacia el andén ---
        if self.state == 'MOVING_TO_LANE':
            
            distance = self.current_position.distance_to(self.target_position)
            
            # Comprobar si ya llegó (con un pequeño margen)
            if distance < 0.1:
                self.current_position = self.target_position
                self.state = 'WAITING_IN_LANE_QUEUE'
                return

            # Calcular movimiento
            direction = (self.target_position - self.current_position).normalize()
            move_distance = self.walk_speed * dt

            if move_distance < distance:
                self.current_position += direction * move_distance
            else:
                # Ha llegado en este frame
                self.current_position = self.target_position
                self.state = WAITING_IN_LANE_QUEUE
        
        # --- Estados Pasivos ---
        elif self.state in ('WAITING_AT_ENTRANCE', 'WAITING_IN_LANE_QUEUE', 'BOARDING', 'IN_TRANSIT', 'ARRIVED'):
            # En estos estados, el pasajero es pasivo.
            # Su posición es estática (esperando) o controlada externamente
            # (por BoardingLane mientras está en 'BOARDING', o irrelevante en 'IN_TRANSIT').
            pass

    def assign_to_lane(self, lane: 'BoardingLane', queue_position: Vector3) -> None:
        """
        Asigna al pasajero a un andén de embarque específico y le da una posición en la cola.
        Cambia el estado del pasajero a MOVING_TO_LANE.

        Args:
            lane (BoardingLane): La instancia del andén de embarque al que se asigna el pasajero.
            queue_position (Vector3): La posición específica en la cola del andén.
        """
        self.current_lane = lane
        self.target_position = queue_position
        self.state = MOVING_TO_LANE

    def start_boarding(self, vehicle: 'ModularVehicle') -> None:
        """
        Inicia el proceso de embarque del pasajero en un vehículo modular.
        Cambia el estado del pasajero a BOARDING.

        Args:
            vehicle (ModularVehicle): La instancia del vehículo modular que el pasajero está abordando.
        """
        self.assigned_vehicle = vehicle
        self.state = BOARDING

    def complete_boarding(self) -> None:
        """
        Completa el proceso de embarque. El pasajero ahora está dentro del vehículo
        y en tránsito. Cambia el estado a IN_TRANSIT.
        """
        self.state = IN_TRANSIT

    def disembark(self) -> None:
        """
        El pasajero desembarca del vehículo en su estación de destino.
        Cambia el estado a ARRIVED y limpia las referencias a la estación, andén y vehículo.
        """
        print(f"🏁 PASAJERO {self.passenger_id} LLEGÓ A SU DESTINO: Estación {self.destination_station_id}")
        self.state = ARRIVED
        self.current_station = None
        self.current_lane = None
        self.assigned_vehicle = None

    def get_info(self) -> Dict[str, Any]:
        """
        Retorna un diccionario con información de depuración del estado actual del pasajero.

        Returns:
            Dict[str, Any]: Un diccionario con el ID, estado, origen, destino y posición del pasajero.
        """
        return {
            "id": self.passenger_id,
            "state": self.state,
            "origin_station_id": self.origin_station_id,
            "destination_station_id": self.destination_station_id,
            "current_position": self.current_position.to_tuple() if self.current_position else None,
            "target_position": self.target_position.to_tuple() if self.target_position else None,
            "current_lane_id": self.current_lane.track_id if self.current_lane else None,
            "assigned_vehicle_id": self.assigned_vehicle.vehicle_id if self.assigned_vehicle else None,
        }