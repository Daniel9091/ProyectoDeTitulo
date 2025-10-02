from objects.base import Vector3

class ModularVehicle:
    """
    VEHÍCULO MODULAR (VM) - UNIDAD BÁSICA DE TRANSPORTE
    
    Responsabilidades:
    - Transportar "pasajeros" (en primera etapa, solo simulado)
    - Moverse a través de la red de tracks bajo coordinación de Brain
    - Seguir rutas asignadas y tomar decisiones de navegación básicas
    - Mantener estado interno (posición, velocidad, destino, etc.)
    
    Características Primera Etapa:
    - No interactúa con pasajeros reales (asignación manual de destinos)
    - Sigue rutas predefinidas por Brain
    - Responde a cambios de estado automáticamente
    """

    def __init__(self, vehicle_id, capacity, initial_position=None):
        self.vehicle_id = vehicle_id
        self.capacity = capacity
        self.passengers = 0  # En primera etapa, simulado
        
        # Estado de posición y movimiento
        self.current_position = initial_position if initial_position else Vector3(0, 0, 0)
        self.velocity = Vector3(0, 0, 0)
        self.current_track = None  # Track actual (StationConnector o AccelerationTree)
        self.progress_on_track = 0.0  # Progreso normalizado en el track actual (0-1)
        
        # Estado del sistema y navegación
        self.state = "docked"  # Estados: docked, moving, accelerating_up, accelerating_down, ready_to_depart
        self.current_station = None  # ID de estación actual si está docked
        self.destination_station = None  # ID de estación destino
        self.target_acceleration_trees = []  # Lista de track_ids objetivo para navegación
        
        # Información operacional
        self.total_distance_traveled = 0.0
        self.operational_time = 0.0
        self.maintenance_required = False
        
        # Configuración de movimiento
        self.max_speed = 25.0  # m/s
        self.acceleration_rate = 2.0  # m/s² (para movimientos propios)
        self.deceleration_rate = 3.0  # m/s²
        
        # Traking
        self._last_progress = 0.0
        
        print(f"Vehículo modular {vehicle_id} creado con capacidad {capacity}")

    def update(self, dt):
        """
        Actualiza el estado del vehículo (llamado por Brain cada frame)
        
        Args:
            dt: Delta time en segundos
        """
        self.operational_time += dt
        
        # Actualizar posición si está en movimiento (principalmente para debug/visualización)
        # El movimiento real lo manejan los tracks, pero mantenemos posición sincronizada
        if self.state in ["moving", "accelerating_up", "accelerating_down"] and self.current_track:
            self.current_position = self.current_track.get_vehicle_position(self)
            self.progress_on_track = self.current_track.get_vehicle_progress(self)
            
            # Actualizar distancia recorrida aproximada
            if hasattr(self.current_track, 'length'):
                distance_this_frame = self.current_track.length * (self.progress_on_track - self._last_progress)
                self.total_distance_traveled += abs(distance_this_frame)
                self._last_progress = self.progress_on_track

    def assign_destination(self, destination_station_id, target_trees=None):
        """
        Asigna un destino al vehículo (manual en primera etapa)
        
        Args:
            destination_station_id: ID de la estación destino
            target_trees: Lista de acceleration trees objetivo (opcional)
        """
        self.destination_station = destination_station_id
        if target_trees:
            self.target_acceleration_trees = target_trees
            
        print(f"Vehículo {self.vehicle_id} asignado a estación destino {destination_station_id}")
        
        # Si está en una estación, cambiar estado para preparar salida
        if self.state == "docked" and self.current_station:
            self.state = "ready_to_depart"

    def board_passengers(self, passenger_count):
        """
        Simula el embarque de pasajeros (en primera etapa, solo contador)
        
        Args:
            passenger_count: Número de pasajeros a embarcar
            
        Returns:
            bool: True si se pudo completar el embarque
        """
        if passenger_count < 0:
            return False
            
        available_capacity = self.capacity - self.passengers
        actual_boarded = min(passenger_count, available_capacity)
        
        if actual_boarded > 0:
            self.passengers += actual_boarded
            print(f"Vehículo {self.vehicle_id}: {actual_boarded} pasajeros embarcados. Total: {self.passengers}/{self.capacity}")
            return True
        else:
            print(f"Vehículo {self.vehicle_id}: Capacidad llena, no se pueden embarcar más pasajeros")
            return False

    def disembark_passengers(self):
        """
        Simula el desembarque de todos los pasajeros
        
        Returns:
            int: Número de pasajeros que desembarcaron
        """
        disembarked = self.passengers
        if disembarked > 0:
            print(f"Vehículo {self.vehicle_id}: {disembarked} pasajeros desembarcados")
            self.passengers = 0
        return disembarked

    def transfer_to_track(self, new_track, entry_velocity=None):
        """
        Transfiere el vehículo a un nuevo track
        
        Args:
            new_track: Nueva instancia de Track
            entry_velocity: Velocidad inicial (opcional)
        """
        # Remover del track actual si existe
        if self.current_track:
            self.current_track.remove_vehicle(self)
        
        # Agregar al nuevo track
        self.current_track = new_track
        new_track.add_vehicle(self, entry_velocity)
        
        # Resetear progreso de seguimiento
        self._last_progress = 0.0
        self.progress_on_track = 0.0
        
        print(f"Vehículo {self.vehicle_id} transferido a track {new_track.track_id}")

    def arrive_at_station(self, station_id):
        """
        Procesa la llegada del vehículo a una estación
        
        Args:
            station_id: ID de la estación de llegada
        """
        self.current_station = station_id
        self.state = "docked"
        self.current_track = None
        self.progress_on_track = 0.0
        
        # Desembarcar pasajeros al llegar
        disembarked = self.disembark_passengers()
        
        # Limpiar destino si llegó a su destino
        if self.destination_station == station_id:
            self.destination_station = None
            self.target_acceleration_trees = []
            print(f"Vehículo {self.vehicle_id} llegó a su destino final: estación {station_id}")
        else:
            print(f"Vehículo {self.vehicle_id} llegó a estación {station_id} (en ruta)")

    def get_vehicle_info(self):
        """
        Retorna información completa del vehículo
        """
        info = {
            "vehicle_id": self.vehicle_id,
            "state": self.state,
            "position": self.current_position.to_tuple(),
            "velocity": self.velocity.to_tuple(),
            "speed": self.velocity.length(),
            "passengers": self.passengers,
            "capacity": self.capacity,
            "occupancy_rate": (self.passengers / self.capacity) * 100 if self.capacity > 0 else 0,
            "current_station": self.current_station,
            "destination_station": self.destination_station,
            "current_track": self.current_track.track_id if self.current_track else None,
            "progress_on_track": self.progress_on_track,
            "total_distance": self.total_distance_traveled,
            "operational_time": self.operational_time,
            "maintenance_required": self.maintenance_required
        }
        
        if self.target_acceleration_trees:
            info["target_trees"] = self.target_acceleration_trees
            
        return info

    def get_status_summary(self):
        """
        Retorna un resumen legible del estado del vehículo
        """
        if self.state == "docked":
            status = f"Docked en estación {self.current_station}"
        elif self.state in ["moving", "accelerating_up", "accelerating_down"]:
            track_type = self.current_track.get_track_type() if self.current_track else "Unknown"
            status = f"{self.state} en {track_type} ({self.progress_on_track*100:.1f}%)"
        else:
            status = self.state
            
        destination_info = f" -> Estación {self.destination_station}" if self.destination_station else " (Sin destino)"
        
        return f"VM {self.vehicle_id}: {status}{destination_info} | Pasajeros: {self.passengers}/{self.capacity}"

    def set_state(self, new_state):
        """
        Cambia el estado del vehículo con validación
        
        Args:
            new_state: Nuevo estado
        """
        valid_states = ["docked", "moving", "accelerating_up", "accelerating_down", "ready_to_depart", "maintenance"]
        
        if new_state in valid_states:
            old_state = self.state
            self.state = new_state
            print(f"Vehículo {self.vehicle_id} cambió estado: {old_state} -> {new_state}")
        else:
            print(f"ERROR: Estado inválido para vehículo {self.vehicle_id}: {new_state}")

    def calculate_travel_time_to_destination(self, network, average_speed=20.0):
        """
        Calcula el tiempo estimado de viaje al destino actual
        
        Args:
            network: Instancia de Network para obtener información de rutas
            average_speed: Velocidad promedio estimada (m/s)
            
        Returns:
            float: Tiempo estimado en segundos, o None si no hay destino
        """
        if not self.destination_station or not self.current_station:
            return None
            
        # Esta es una estimación simple. En una implementación completa,
        # se usaría el algoritmo de ruta de Brain para calcular distancia exacta
        if self.current_station == self.destination_station:
            return 0.0
            
        # Estimación basada en distancia lineal entre estaciones
        # En el futuro, esto se reemplazará con cálculos de ruta reales
        current_station_pos = Vector3(0, 0, 0)  # Esto debería obtenerse de Brain
        destination_station_pos = Vector3(0, 0, 0)  # Esto debería obtenerse de Brain
        
        linear_distance = current_station_pos.distance_to(destination_station_pos)
        
        # Factor de ruta (las rutas reales son más largas que la distancia lineal)
        route_factor = 1.3  # 30% más largo por rutas indirectas
        
        estimated_distance = linear_distance * route_factor
        estimated_time = estimated_distance / average_speed
        
        return estimated_time

    def request_maintenance(self):
        """
        Marca el vehículo como necesitando mantenimiento
        """
        self.maintenance_required = True
        self.state = "maintenance"
        print(f"Vehículo {self.vehicle_id} requiere mantenimiento")

    def complete_maintenance(self):
        """
        Completa el mantenimiento del vehículo
        """
        self.maintenance_required = False
        self.state = "docked"
        print(f"Vehículo {self.vehicle_id} completó mantenimiento")

    def _update_velocity_from_track(self):
        """
        Actualiza la velocidad del vehículo basado en el track actual
        (Método interno para sincronización)
        """
        if self.current_track and hasattr(self.current_track, 'get_vehicle_velocity'):
            track_speed = self.current_track.get_vehicle_velocity(self)
            direction = self.current_track.get_direction_vector()
            self.velocity = direction * track_speed

    def get_energy_consumption(self, time_period):
        """
        Calcula el consumo energético estimado para un período
        
        Args:
            time_period: Período de tiempo en segundos
            
        Returns:
            float: Consumo energético estimado en kWh
        """
        # Fórmula simplificada: consumo base + consumo por distancia + consumo por pasajero
        base_consumption = 0.1  # kWh por segundo operativo
        distance_consumption = 0.2  # kWh por metro
        passenger_consumption = 0.01  # kWh por pasajero por segundo
        
        distance_in_period = self.velocity.length() * time_period
        
        consumption = (base_consumption * time_period + 
                      distance_consumption * distance_in_period + 
                      passenger_consumption * self.passengers * time_period)
        
        return consumption

    def is_operational(self):
        """
        Verifica si el vehículo está operativo
        
        Returns:
            bool: True si está operativo, False si necesita mantenimiento
        """
        return not self.maintenance_required and self.state != "maintenance"