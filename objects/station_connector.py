from objects.track import Track
from objects.base import Vector3

class StationConnector(Track):
    """
    VÍA SUBTERRÁNEA RECTA ENTRE DOS PUNTOS
    
    Características:
    - Movimiento lineal a velocidad constante
    - Progreso uniforme a lo largo del tramo
    - Velocidad constante (configurable, 20 m/s por defecto)
    - Transiciones suaves entre tracks
    """
    
    def __init__(self, track_id, start_pos, end_pos, speed=20.0):
        super().__init__(track_id, start_pos, end_pos)
        self.speed = speed  # m/s constante
        self.direction = self.get_direction_vector()
        
    def add_vehicle(self, vehicle, entry_velocity=None):
        """
        Agrega un vehículo al StationConnector
        
        Args:
            vehicle: Instancia de ModularVehicle
            entry_velocity: Se ignora - siempre comienza con velocidad constante
        """
        # Inicializar vehículo al inicio del track
        self.vehicles[vehicle.vehicle_id] = {
            'vehicle': vehicle,
            'progress': 0.0,
            'velocity': self.speed,
            'current_position': self.start_pos
        }
        
        # Actualizar estado del vehículo
        vehicle.current_track = self
        vehicle.state = "moving"
        
        print(f"Vehículo {vehicle.vehicle_id} entró a StationConnector {self.track_id}")
    
    def remove_vehicle(self, vehicle):
        """Remueve un vehículo del StationConnector"""
        if vehicle.vehicle_id in self.vehicles:
            del self.vehicles[vehicle.vehicle_id]
            print(f"Vehículo {vehicle.vehicle_id} salió de StationConnector {self.track_id}")
    
    def update_vehicles(self, dt):
        """
        Actualiza la posición de todos los vehículos en el connector
        
        Returns:
            Lista de vehículos que completaron el track
        """
        completed_vehicles = []
        
        for vehicle_id, vehicle_data in list(self.vehicles.items()):
            vehicle = vehicle_data['vehicle']
            progress = vehicle_data['progress']
            
            # Calcular nuevo progreso (movimiento lineal)
            distance_traveled = self.speed * dt
            progress_increment = distance_traveled / self.length
            new_progress = progress + progress_increment
            
            # Limitar a 1.0 (fin del track)
            if new_progress >= 1.0:
                new_progress = 1.0
                completed_vehicles.append(vehicle)
            
            # Actualizar datos del vehículo
            self.vehicles[vehicle_id]['progress'] = new_progress
            self.vehicles[vehicle_id]['current_position'] = self.calculate_position_at_progress(new_progress)
            
            # Actualizar posición en el vehículo también
            vehicle.current_position = self.vehicles[vehicle_id]['current_position']
        
        return completed_vehicles
    
    def get_vehicle_position(self, vehicle):
        """Obtiene la posición 3D actual del vehículo"""
        if vehicle.vehicle_id in self.vehicles:
            return self.vehicles[vehicle.vehicle_id]['current_position']
        return self.start_pos
    
    def get_vehicle_progress(self, vehicle):
        """Obtiene el progreso normalizado del vehículo (0 a 1)"""
        if vehicle.vehicle_id in self.vehicles:
            return self.vehicles[vehicle.vehicle_id]['progress']
        return 0.0
    
    def get_exit_position(self):
        """Posición de salida del track (final del connector)"""
        return self.end_pos
    
    def get_exit_velocity(self, vehicle):
        """Velocidad de salida del vehículo (constante)"""
        return self.direction * self.speed
    
    def get_connector_info(self):
        """Información específica del StationConnector"""
        base_status = self.get_status()
        base_status.update({
            "speed": self.speed,
            "direction": self.direction.to_tuple(),
            "vehicle_details": {
                vid: {
                    "progress": data['progress'],
                    "position": data['current_position'].to_tuple()
                } for vid, data in self.vehicles.items()
            }
        })
        return base_status

    ## Funciones Adicionales ##

    def set_speed(self, new_speed):
        """Cambia la velocidad del connector (útil para ajustes en simulación)"""
        self.speed = new_speed
        print(f"StationConnector {self.track_id} velocidad cambiada a {new_speed} m/s")
    
    def get_travel_time(self):
        """Calcula el tiempo de viaje completo a través del connector"""
        return self.length / self.speed if self.speed > 0 else float('inf')
    
    def get_remaining_distance(self, vehicle):
        """Calcula la distancia restante para un vehículo específico"""
        progress = self.get_vehicle_progress(vehicle)
        return self.length * (1.0 - progress)