from objects.track import Track
from objects.base import Vector3
import math

class AccelerationTree(Track):
    """
    RAMPA DE ACELERACIÓN/DESACELERACIÓN CON FÍSICA REAL
    
    Características:
    - Movimiento con aceleración basada en el ángulo de inclinación
    - Aceleración = g * sin(θ) donde θ es el ángulo de la rampa
    - Dirección: 'up' (subida) o 'down' (bajada)
    - Sin roce (gravedad pura)
    - Velocidad variable según la inclinación real
    """
    
    def __init__(self, track_id, start_pos, end_pos, direction, station_id=None):
        super().__init__(track_id, start_pos, end_pos)
        self.direction = direction  # 'up' o 'down'
        self.gravity = 9.8  # m/s²
        self.station_id = station_id
        

        # CALCULAR ÁNGULO DE INCLINACIÓN REAL
        self.angle, self.sin_angle = self._calculate_ramp_angle()
        
        # CALCULAR ACELERACIÓN REAL BASADA EN EL ÁNGULO
        if self.direction == 'down':
            self.acceleration = self.gravity * self.sin_angle  # a = g * sin(θ)
            self.initial_velocity = 0.0  # Comienza desde reposo
        else:  # 'up'
            self.acceleration = -self.gravity * self.sin_angle  # a = -g * sin(θ)
            self.initial_velocity = 20.0  # Velocidad de los StationConnector
        
        # Calcular velocidad final teórica
        self.final_velocity = self._calculate_final_velocity()

    def get_station_id(self):
        """
        Obtiene el ID de la estación asociada a este árbol de aceleración
        
        Returns:
            str o int: ID de la estación, o None si no está asignado
        """
        if self.station_id is None:
            print(f"ADVERTENCIA: AccelerationTree {self.track_id} no tiene station_id asignado")
        return self.station_id

    def _calculate_ramp_angle(self):
        """
        Calcula el ángulo de inclinación real de la rampa
        
        Returns:
            tuple: (angle_radians, sin_angle)
        """
        # Calcular diferencia de altura (cateto opuesto)
        delta_z = abs(self.end_pos.z - self.start_pos.z)
        
        # Calcular distancia horizontal (cateto adyacente)
        delta_x = self.end_pos.x - self.start_pos.x
        delta_y = self.end_pos.y - self.start_pos.y
        horizontal_distance = math.sqrt(delta_x**2 + delta_y**2)
        
        if horizontal_distance > 0:
            # Ángulo = arctan(altura / distancia_horizontal)
            angle_radians = math.atan2(delta_z, horizontal_distance)
            sin_angle = math.sin(angle_radians)
        else:
            # Si no hay distancia horizontal, es vertical (90°)
            angle_radians = math.pi / 2
            sin_angle = 1.0
        
        return angle_radians, sin_angle
    
    def _calculate_final_velocity(self):
        """Calcula la velocidad final usando ecuaciones de MRUA"""
        # v² = u² + 2as
        v_squared = self.initial_velocity**2 + 2 * self.acceleration * self.length
        return math.sqrt(max(0, v_squared))
    
    def add_vehicle(self, vehicle, entry_velocity=None):
        """
        Agrega un vehículo al AccelerationTree
        
        Args:
            vehicle: Instancia de ModularVehicle
            entry_velocity: Velocidad inicial (opcional)
        """
        # Usar entry_velocity si se proporciona, de lo contrario la velocidad por defecto
        initial_velocity = entry_velocity if entry_velocity is not None else self.initial_velocity
        
        self.vehicles[vehicle.vehicle_id] = {
            'vehicle': vehicle,
            'progress': 0.0,
            'velocity': initial_velocity,
            'current_position': self.start_pos,
            'time_in_track': 0.0
        }
        
        # Actualizar estado del vehículo
        vehicle.current_track = self
        vehicle.state = "accelerating_down" if self.direction == 'down' else "accelerating_up"
        
        print(f"Vehículo {vehicle.vehicle_id} entró a AccelerationTree {self.track_id}")
        print(f"  Dirección: {self.direction}, Ángulo: {math.degrees(self.angle):.1f}°, Aceleración: {self.acceleration:.2f} m/s²")
    
    def remove_vehicle(self, vehicle):
        """Remueve un vehículo del AccelerationTree"""
        if vehicle.vehicle_id in self.vehicles:
            del self.vehicles[vehicle.vehicle_id]
            print(f"Vehículo {vehicle.vehicle_id} salió de AccelerationTree {self.track_id}")
    
    def update_vehicles(self, dt):
        """
        Actualiza la posición de todos los vehículos en el árbol usando MRUA
        
        Returns:
            Lista de vehículos que completaron el track
        """
        completed_vehicles = []
        
        for vehicle_id, vehicle_data in list(self.vehicles.items()):
            vehicle = vehicle_data['vehicle']
            progress = vehicle_data['progress']
            current_velocity = vehicle_data['velocity']
            time_in_track = vehicle_data['time_in_track']
            
            # Calcular nueva velocidad (v = u + at)
            new_velocity = current_velocity + self.acceleration * dt
            
            # Limitar velocidad mínima a 0 (no velocidades negativas)
            if self.direction == 'up' and new_velocity < 0:
                new_velocity = 0
            
            # Calcular distancia recorrida en este paso (s = ut + ½at²)
            distance_traveled = current_velocity * dt + 0.5 * self.acceleration * dt**2
            
            # Calcular nuevo progreso
            progress_increment = distance_traveled / self.length
            new_progress = progress + progress_increment
            new_time = time_in_track + dt
            
            # Si completó el track
            if new_progress >= 1.0:
                new_progress = 1.0
                completed_vehicles.append(vehicle)
            
            # Actualizar datos del vehículo
            self.vehicles[vehicle_id]['progress'] = new_progress
            self.vehicles[vehicle_id]['velocity'] = new_velocity
            self.vehicles[vehicle_id]['time_in_track'] = new_time
            self.vehicles[vehicle_id]['current_position'] = self.calculate_position_at_progress(new_progress)
            
            # Actualizar posición y velocidad en el vehículo
            vehicle.current_position = self.vehicles[vehicle_id]['current_position']
            vehicle.velocity = self.get_direction_vector() * new_velocity
        
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
    
    def get_vehicle_velocity(self, vehicle):
        """Obtiene la velocidad actual del vehículo"""
        if vehicle.vehicle_id in self.vehicles:
            return self.vehicles[vehicle.vehicle_id]['velocity']
        return self.initial_velocity
    
    def get_exit_position(self):
        """Posición de salida del track (final del árbol)"""
        return self.end_pos
    
    def get_exit_velocity(self, vehicle):
        """
        Velocidad de salida del vehículo
        
        Returns:
            Vector3 con dirección y magnitud de la velocidad de salida
        """
        if vehicle.vehicle_id in self.vehicles:
            exit_speed = self.vehicles[vehicle.vehicle_id]['velocity']
        else:
            exit_speed = self.final_velocity
        
        direction = self.get_direction_vector()
        return direction * exit_speed
    
    def get_angle_degrees(self):
        """Retorna el ángulo de la rampa en grados"""
        return math.degrees(self.angle)
    
    def get_ramp_info(self):
        """Información detallada de la rampa"""
        base_status = self.get_status()
        base_status.update({
            "direction": self.direction,
            "angle_degrees": self.get_angle_degrees(),
            "sin_angle": self.sin_angle,
            "acceleration": self.acceleration,
            "initial_velocity": self.initial_velocity,
            "final_velocity": self.final_velocity,
            "height_difference": abs(self.end_pos.z - self.start_pos.z),
            "horizontal_distance": math.sqrt(
                (self.end_pos.x - self.start_pos.x)**2 + 
                (self.end_pos.y - self.start_pos.y)**2
            ),
            "vehicle_details": {
                vid: {
                    "progress": data['progress'],
                    "velocity": data['velocity'],
                    "position": data['current_position'].to_tuple(),
                    "time_in_track": data['time_in_track']
                } for vid, data in self.vehicles.items()
            }
        })
        return base_status
    
    def get_time_to_complete(self, initial_velocity=None):
        """
        Calcula el tiempo teórico para completar el árbol
        
        Returns:
            Tiempo en segundos, o None si no es posible (subida con velocidad insuficiente)
        """
        v0 = initial_velocity if initial_velocity is not None else self.initial_velocity
        
        # Resolver: s = v0*t + ½a*t²
        # ½a*t² + v0*t - s = 0
        a = self.acceleration
        discriminant = v0**2 + 2 * a * self.length
        
        if discriminant < 0:
            return None  # No hay solución real
            
        t1 = (-v0 + math.sqrt(discriminant)) / a
        t2 = (-v0 - math.sqrt(discriminant)) / a
        
        # Devolver el tiempo positivo
        return max(t1, t2) if t1 > 0 and t2 > 0 else (t1 if t1 > 0 else t2)