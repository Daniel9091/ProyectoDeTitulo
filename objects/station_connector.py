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
    
    def update_vehicles(self, dt, exclude_vehicles=None):
        """
        Actualiza la posición de todos los vehículos en el connector
        
        Returns:
            Lista de tuplas (vehículo, tiempo_sobrante) que completaron el track
        """
        completed_vehicles = []
        if exclude_vehicles is None:
            exclude_vehicles = set()
        
        for vehicle_id, vehicle_data in list(self.vehicles.items()):
            if vehicle_id in exclude_vehicles:
                continue
            vehicle = vehicle_data['vehicle']
            time_left = self.update_vehicle_progress(vehicle, dt)
            
            # Si time_left es mayor que 0, el vehículo ha completado el track.
            if time_left > 0:
                completed_vehicles.append((vehicle, time_left))
        
        return completed_vehicles

    def update_vehicle_progress(self, vehicle, time_delta):
        """
        Actualiza el progreso de un solo vehículo por un delta de tiempo.
        Devuelve el tiempo sobrante si el vehículo completa el track.
        """
        if vehicle.vehicle_id not in self.vehicles:
            return 0.0

        vehicle_data = self.vehicles[vehicle.vehicle_id]
        progress = vehicle_data['progress']
        
        # Si ya está al final, no hacer nada.
        if progress >= 1.0:
            return time_delta

        # --- ¡SOLUCIÓN! ---
        # Usar la velocidad específica del vehículo, que puede ser diferente
        # si acaba de entrar desde una rampa.
        vehicle_speed = vehicle_data.get('velocity', self.speed)
        distance_to_travel = vehicle_speed * time_delta
        progress_increment = distance_to_travel / self.length if self.length > 0 else 0
        new_progress = progress + progress_increment
        
        time_left = 0.0
        if new_progress >= 1.0:
            # Calcular el tiempo sobrante
            if vehicle_speed > 0:
                time_to_reach_end = ((1.0 - progress) * self.length) / vehicle_speed
                time_left = time_delta - time_to_reach_end
            new_progress = 1.0
            
        # Actualizar datos del vehículo
        vehicle_data['progress'] = new_progress
        vehicle_data['current_position'] = self.calculate_position_at_progress(new_progress)
        vehicle.current_position = vehicle_data['current_position']

        return max(0.0, time_left)
    
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