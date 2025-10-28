from objects.track import Track
from objects.base import Vector3
import math

class AccelerationTree(Track):
    """
    RAMPA DE ACELERACIÓN/DESACELERACIÓN CON FÍSICA REAL Y CONTROL DE DENSIDAD
    
    Responsabilidades PRINCIPALES:
    - Gestionar movimiento con física real (MRUA)
    - Controlar densidad de vehículos para seguridad
    - Proporcionar información de estado y capacidad
    
    Responsabilidades NO incluidas:
    - Toma de decisiones de routing (lo hace TreeSelector)
    - Gestión de pasajeros (lo hace Station/Brain)
    - Navegación entre tracks (lo hace Network)
    """

    def __init__(self, track_id, start_pos, end_pos, direction, station_id=None):
        super().__init__(track_id, start_pos, end_pos)
        self.direction = direction                  # 'up' o 'down'
        self.gravity = 9.8                          # m/s²
        self.station_id = station_id
        
        # CONFIGURACIÓN DE DENSIDAD - NUEVO
        self.min_safe_distance = 40.0       # ✅ AUMENTADO: Mayor distancia para evitar colisiones en la estación
        self.max_concurrent_vehicles = 50    # máximo de VMs simultáneos
        
        # CALCULAR ÁNGULO DE INCLINACIÓN REAL (existente)
        self.angle, self.sin_angle = self._calculate_ramp_angle()
        
        # CALCULAR ACELERACIÓN REAL BASADA EN EL ÁNGULO (existente)
        if self.direction == 'down':
            self.acceleration = self.gravity * self.sin_angle  # a = g * sin(θ)
            self.initial_velocity = 0.0  # Comienza desde reposo
        else:  # 'up'
            self.acceleration = -self.gravity * self.sin_angle  # a = -g * sin(θ)
            self.initial_velocity = 20.0  # Velocidad de los StationConnector
        
        # Calcular velocidad final teórica (existente)
        self.final_velocity = self._calculate_final_velocity()

    # ========== MÉTODOS DE CONTROL DE DENSIDAD ==========

    def can_accept_vehicle(self, vehicle):
        """
        Verifica si el árbol puede aceptar un nuevo vehículo de forma segura
        
        Args:
            vehicle: Vehículo a verificar (no se usa directamente, pero se mantiene para futura extensión)
            
        Returns:
            bool: True si puede aceptar el vehículo de forma segura
        """

        # 1. Los arboles de bajada ('down') siempre pueden aceptar vehículos
        if self.direction == 'down':
            return True


        # 1. Verificar límite máximo absoluto de vehículos (solo para 'up')
        if len(self.vehicles) >= self.max_concurrent_vehicles:
            return False
            
        # 2. Verificar distancia segura con el vehículo más cercano al inicio
        if self.vehicles:
            closest_distance_to_start = min(
                vehicle_data['progress'] * self.length 
                for vehicle_data in self.vehicles.values()
            )
            
            # Si el vehículo más cercano está muy cerca del inicio, rechazar
            if closest_distance_to_start < self.min_safe_distance:
                return False
                
        return True

    def get_occupancy_info(self):
        """
        Retorna información de ocupación del árbol para monitoreo
        
        Returns:
            dict: Información sobre capacidad y ocupación actual
        """
        return {
            'vehicle_count': len(self.vehicles),
            'max_vehicles': self.max_concurrent_vehicles,
            'occupancy_rate': len(self.vehicles) / self.max_concurrent_vehicles,
            'available': self.can_accept_vehicle(None)  # Verificación genérica
        }

    # ========== MÉTODOS MODIFICADOS PARA INTEGRAR CONTROL DE DENSIDAD ==========

    def add_vehicle(self, vehicle, entry_velocity=None):
        """
        Agrega un vehículo al AccelerationTree CON VERIFICACIÓN DE SEGURIDAD
        
        Args:
            vehicle: Instancia de ModularVehicle
            entry_velocity: Velocidad inicial (opcional)
            
        Returns:
            bool: True si se pudo agregar, False si fue rechazado por seguridad
        """
        # VERIFICACIÓN DE SEGURIDAD - NUEVO
        if not self.can_accept_vehicle(vehicle):
            print(f"Rechazado: Vehículo {vehicle.vehicle_id} no puede entrar a árbol {self.track_id} - Densidad insegura")
            return False
            
        # CONTINUAR CON LÓGICA EXISTENTE (sin cambios)
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
        
        return True  # Éxito

    # ========== MÉTODOS EXISTENTES (SIN CAMBIOS SIGNIFICATIVOS) ==========

    def get_station_id(self):
        """Obtiene el ID de la estación asociada"""
        if self.station_id is None:
            print(f"ADVERTENCIA: AccelerationTree {self.track_id} no tiene station_id asignado")
        return self.station_id

    def _calculate_ramp_angle(self):
        """Calcula el ángulo de inclinación real de la rampa (existente)"""
        delta_z = abs(self.end_pos.z - self.start_pos.z)
        delta_x = self.end_pos.x - self.start_pos.x
        delta_y = self.end_pos.y - self.start_pos.y
        horizontal_distance = math.sqrt(delta_x**2 + delta_y**2)
        
        if horizontal_distance > 0:
            angle_radians = math.atan2(delta_z, horizontal_distance)
            sin_angle = math.sin(angle_radians)
        else:
            angle_radians = math.pi / 2
            sin_angle = 1.0
        
        return angle_radians, sin_angle
    
    def _calculate_final_velocity(self):
        """Calcula la velocidad final usando ecuaciones de MRUA (existente)"""
        v_squared = self.initial_velocity**2 + 2 * self.acceleration * self.length
        return math.sqrt(max(0, v_squared))

    def remove_vehicle(self, vehicle):
        """Remueve un vehículo del AccelerationTree (existente)"""
        if vehicle.vehicle_id in self.vehicles:
            del self.vehicles[vehicle.vehicle_id]

    def update_vehicles(self, dt):
        """Actualiza posición de vehículos usando MRUA (existente)"""
        completed_vehicles = []
        
        for vehicle_id, vehicle_data in list(self.vehicles.items()):
            vehicle = vehicle_data['vehicle']
            progress = vehicle_data['progress']
            current_velocity = vehicle_data['velocity']
            time_in_track = vehicle_data['time_in_track']
            
            # Física MRUA (existente)
            new_velocity = current_velocity + self.acceleration * dt
            
            # Limitar velocidad mínima a 0
            if self.direction == 'up' and new_velocity < 0:
                new_velocity = 0
            
            distance_traveled = current_velocity * dt + 0.5 * self.acceleration * dt**2
            progress_increment = distance_traveled / self.length
            new_progress = progress + progress_increment
            new_time = time_in_track + dt
            
            if new_progress >= 1.0:
                new_progress = 1.0
                completed_vehicles.append(vehicle)
            
            # Actualizar datos
            self.vehicles[vehicle_id]['progress'] = new_progress
            self.vehicles[vehicle_id]['velocity'] = new_velocity
            self.vehicles[vehicle_id]['time_in_track'] = new_time
            self.vehicles[vehicle_id]['current_position'] = self.calculate_position_at_progress(new_progress)
            
            # Actualizar vehículo
            vehicle.current_position = self.vehicles[vehicle_id]['current_position']
            vehicle.velocity = self.get_direction_vector() * new_velocity
        
        return completed_vehicles

    # ========== MÉTODOS DE CONSULTA (existentes, sin cambios) ==========

    def get_vehicle_position(self, vehicle):
        if vehicle.vehicle_id in self.vehicles:
            return self.vehicles[vehicle.vehicle_id]['current_position']
        return self.start_pos
    
    def get_vehicle_progress(self, vehicle):
        if vehicle.vehicle_id in self.vehicles:
            return self.vehicles[vehicle.vehicle_id]['progress']
        return 0.0
    
    def get_vehicle_velocity(self, vehicle):
        if vehicle.vehicle_id in self.vehicles:
            return self.vehicles[vehicle.vehicle_id]['velocity']
        return self.initial_velocity
    
    def get_exit_position(self):
        return self.end_pos
    
    def get_exit_velocity(self, vehicle):
        if vehicle.vehicle_id in self.vehicles:
            exit_speed = self.vehicles[vehicle.vehicle_id]['velocity']
        else:
            exit_speed = self.final_velocity
        
        direction = self.get_direction_vector()
        return direction * exit_speed
    
    def get_angle_degrees(self):
        return math.degrees(self.angle)
    
    def get_ramp_info(self):
        """Información detallada de la rampa (mejorada con datos de densidad)"""
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
            # NUEVO: Información de densidad
            "min_safe_distance": self.min_safe_distance,
            "max_concurrent_vehicles": self.max_concurrent_vehicles,
            "current_vehicles": len(self.vehicles),
            "can_accept_new": self.can_accept_vehicle(None),
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
        """Calcula tiempo teórico para completar el árbol (existente)"""
        v0 = initial_velocity if initial_velocity is not None else self.initial_velocity
        a = self.acceleration
        discriminant = v0**2 + 2 * a * self.length
        
        if discriminant < 0:
            return None
            
        # Soluciones de la ecuación cuadrática para el tiempo
        t1 = (-v0 + math.sqrt(discriminant)) / a
        t2 = (-v0 - math.sqrt(discriminant)) / a
        
        # Filtrar solo las soluciones positivas (físicamente posibles)
        positive_times = []
        if t1 > 0:
            positive_times.append(t1)
        if t2 > 0:
            positive_times.append(t2)

        # Si hay soluciones positivas, devolver la más pequeña.
        # La solución más pequeña es la primera vez que el objeto alcanza la posición.
        if positive_times:
            return min(positive_times)
        
        return None # No hay un tiempo de viaje positivo posible