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
          
    def remove_vehicle(self, vehicle):
        """Remueve un vehículo del StationConnector"""
        if vehicle.vehicle_id in self.vehicles:
            del self.vehicles[vehicle.vehicle_id]
    
    def update_vehicles(self, dt):
        """
        Actualiza la posición de todos los vehículos en el connector
        
        Returns:
            Lista de vehículos que completaron el track
        """
        completed_vehicles = []
        finished_vehicles_data = []
        
        for vehicle_id, vehicle_data in list(self.vehicles.items()):
            vehicle = vehicle_data['vehicle']
            progress = vehicle_data['progress']
            finished_data = self.update_single_vehicle(vehicle, dt)
            if finished_data:
                finished_vehicles_data.append(finished_data)
        
        return finished_vehicles_data

    def update_single_vehicle(self, vehicle, dt):
        """Actualiza un solo vehículo y devuelve datos si termina."""
        if vehicle.vehicle_id not in self.vehicles:
            return None

        vehicle_data = self.vehicles[vehicle.vehicle_id]
        progress = vehicle_data['progress']
        
        distance_to_travel = self.speed * dt
        progress_increment = distance_to_travel / self.length if self.length > 0 else 0
        new_progress = progress + progress_increment
        
        time_left = 0
        if new_progress >= 1.0:
            # Calcular el tiempo sobrante
            distance_over = (new_progress - 1.0) * self.length
            time_over = distance_over / self.speed if self.speed > 0 else 0
            time_left = dt - (dt - time_over)

            new_progress = 1.0
            
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
        # Actualizar datos del vehículo
        vehicle_data['progress'] = new_progress
        vehicle_data['current_position'] = self.calculate_position_at_progress(new_progress)
        vehicle.current_position = vehicle_data['current_position']

        if new_progress >= 1.0:
            return {
                'vehicle': vehicle,
                'time_left': time_left
            }
        return None
    
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
    
    def get_vehicle_velocity(self, vehicle):
        """Obtiene la velocidad del vehículo en este track (constante)."""
        # Para un StationConnector, la velocidad es siempre la misma.
        return self.speed

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