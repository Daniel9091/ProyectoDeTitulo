from objects.station_connector import StationConnector
from typing import TYPE_CHECKING, List, Dict
from objects.base import Vector3 # Asegúrate de que Vector3 esté importado

if TYPE_CHECKING:
    from objects.stations import Station
    from objects.passenger import Passenger
    from objects.modular_vehicles import ModularVehicle


class BoardingLane(StationConnector):
    """
    ANDÉN DE EMBARQUE DENTRO DE UNA ESTACIÓN.
    
    Es un tipo especializado de StationConnector con una velocidad reducida
    y la capacidad de gestionar el embarque y desembarque de pasajeros.
    
    Un vehículo que se encuentre en este tipo de track NO es elegible
    para ser asignado a una nueva demanda de otra estación.
    """
    
    def __init__(self, track_id, start_pos, end_pos, speed=2.0):
        # Llama al constructor de la clase padre (StationConnector)
        super().__init__(track_id, start_pos, end_pos, speed)
        
        # Atributos específicos del andén
        self.is_boarding_platform = True
        
        # --- NUEVOS ATRIBUTOS FASE 3 ---
        self.station: 'Station' = None # Referencia a la estación propietaria
        self.passenger_wait_queue: List['Passenger'] = [] # Pasajeros esperando EN el andén
        self.passengers_boarding: Dict[str, 'Passenger'] = {} # vehicle_id -> Passenger (pasajeros en proceso de embarque)
        # --- FIN NUEVOS ATRIBUTOS ---

    def get_track_type(self):
        """Sobrescribe el tipo de track para identificación."""
        return "BoardingLane"

    def set_station(self, station: 'Station'):
        """Inyecta la dependencia de la estación (llamado por SimulationBuilder)."""
        self.station = station

    def get_queue_start_position(self) -> 'Vector3':
        """Retorna la posición física donde los pasajeros deben esperar."""
        # Por ahora, es justo al inicio del andén.
        return self.start_pos

    def add_passenger_to_queue(self, passenger: 'Passenger', queue_position: 'Vector3'):
        """Añade un pasajero (que acaba de llegar a pie) a la cola de espera del andén."""
        # 1. Asignar al pasajero el objetivo de caminar hacia la cola
        passenger.assign_to_lane(self, queue_position)
        
        # 2. Añadirlo a la lista de espera del andén
        self.passenger_wait_queue.append(passenger)

    def add_vehicle(self, vehicle: 'ModularVehicle', entry_velocity=None):
        """
        Sobrescribe el método de la clase padre para iniciar el "rendezvous" del pasajero.
        """
        # 1. Dejar que la clase padre añada el vehículo (esto lo pone en self.vehicles)
        super().add_vehicle(vehicle, entry_velocity)

        if not self.station:
            print(f"ERROR: Andén {self.track_id} no tiene estación asignada.")
            return

        # 2. Comprobar si hay pasajeros esperando en ESTE andén
        if not self.passenger_wait_queue:
            # No hay pasajeros. El VM simplemente pasará de largo.
            return
            
        # 3. Hay un pasajero. Iniciar el embarque.
        passenger = self.passenger_wait_queue.pop(0) # Sacar al primero de la fila
        
        # 4. "Enganchar" al pasajero al VM
        self.passengers_boarding[vehicle.vehicle_id] = passenger
        
        # 5. Notificar al pasajero que está embarcando
        passenger.start_boarding(vehicle)
        

    def remove_vehicle(self, vehicle: 'ModularVehicle'):
        """
        Sobrescribe el método de la clase padre para limpiar pasajeros
        que pudieran haber estado embarcando.
        """
        # 1. Limpiar al pasajero "enganchado", si existe
        passenger = self.passengers_boarding.pop(vehicle.vehicle_id, None)
        
        if passenger:
            # El vehículo se fue ANTES de completar el embarque (progress < 0.5)
            # Debemos re-encolar al pasajero.
            print(f"ADVERTENCIA: VM {vehicle.vehicle_id} salió del andén. Re-encolando a P:{passenger.passenger_id}.")
            passenger.state = "WAITING_IN_LANE_QUEUE"
            # Ponerlo de nuevo al inicio de la fila de espera
            self.passenger_wait_queue.insert(0, passenger)
            
        # 2. Llamar al método de la clase padre para remover el vehículo
        super().remove_vehicle(vehicle)

    def update_vehicles(self, dt: float, exclude_vehicles=None) -> list:
        """
        Sobrescribe el método de la clase padre para sincronizar las posiciones
        de los pasajeros durante el embarque en movimiento.
        """
        # 1. Mover todos los vehículos en el andén (lógica de StationConnector)
        completed_vehicles = super().update_vehicles(dt, exclude_vehicles=exclude_vehicles)
        
        # 2. Sincronizar pasajeros que están embarcando
        for vehicle_id, passenger in list(self.passengers_boarding.items()):
            
            # 2a. Obtener los datos del vehículo (posición, progreso)
            vehicle_data = self.vehicles.get(vehicle_id)
            
            # 2b. Comprobación de seguridad (si el VM ya no está, limpiar)
            if not vehicle_data:
                print(f"ERROR: VM {vehicle_id} desapareció durante embarque de {passenger.passenger_id}")
                del self.passengers_boarding[vehicle_id]
                continue
                
            vehicle = vehicle_data['vehicle']
            
            # 2c. ¡LA SINCRONIZACIÓN! Forzar la posición del pasajero
            passenger.current_position = vehicle_data['current_position']
            
            # 2d. Comprobar si el embarque se debe completar
            progress = vehicle_data['progress']
            if progress >= 0.5: # Punto de "commit" (50% del andén)
                self._complete_boarding(passenger, vehicle)
                
        return completed_vehicles

    def _complete_boarding(self, passenger: 'Passenger', vehicle: 'ModularVehicle'):
        """
        Finaliza el proceso de embarque de un pasajero en un vehículo.
        """
        
        # 1. Notificar al pasajero que está 'IN_TRANSIT'
        passenger.complete_boarding()
        
        # 2. Actualizar la cuenta de pasajeros del VM
        vehicle.board_passengers(passenger) # ✅ PASAR EL OBJETO PASAJERO REAL
        
        # 3. ¡ACCIÓN CLAVE! Asignar el destino del pasajero al VM, incluyendo los árboles objetivo.
        brain = None
        # Accedemos al Brain a través de la cadena de referencias: Lane -> Station -> TreeSelector -> Brain
        if self.station and hasattr(self.station, 'tree_selector') and self.station.tree_selector:
            brain = self.station.tree_selector.brain

        if brain:
            # Obtener los árboles de llegada óptimos para la estación de destino del pasajero
            target_trees = brain._find_optimal_target_trees(passenger.destination_station_id, vehicle) # type: ignore
            vehicle.assign_destination(passenger.destination_station_id, target_trees)
        else:
            # Fallback si no se puede acceder al Brain
            print(f"ADVERTENCIA: No se pudo asignar target_trees al VM {vehicle.vehicle_id} porque Brain no está disponible.")
            vehicle.assign_destination(passenger.destination_station_id) # Fallback sin árboles específicos
        
        # 4. Quitar al pasajero de la lista de embarque activo
        # (usamos .pop() para eliminarlo de forma segura)
        self.passengers_boarding.pop(vehicle.vehicle_id, None)