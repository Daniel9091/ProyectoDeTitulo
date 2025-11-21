from abc import ABC, abstractmethod
from objects.base import Vector3

class Track(ABC):
    """
    CLASE BASE ABSTRACTA PARA TODOS LOS TIPOS DE VÍAS
    
    Responsabilidades comunes:
    - Gestionar vehículos en el tramo
    - Actualizar posiciones de vehículos
    - Determinar cuándo un vehículo completa el tramo
    - Proporcionar información de posición y estado
    
    Debe ser implementada por:
    - StationConnector (vías subterráneas rectas)
    - AccelerationTree (rampas de aceleración/desaceleración)
    """
    
    def __init__(self, track_id, start_pos, end_pos):
        self.track_id = track_id
        self.start_pos = start_pos  # Vector3
        self.end_pos = end_pos      # Vector3
        self.length = start_pos.distance_to(end_pos)
        self.vehicles = {}  # vehicle_id -> (vehicle, progress, velocity, etc.)
        
    @abstractmethod
    def add_vehicle(self, vehicle, entry_velocity=None):
        """
        Agrega un vehículo al track
        
        Args:
            vehicle: Instancia de ModularVehicle
            entry_velocity: Velocidad inicial (opcional)
        """
        pass
    
    @abstractmethod
    def remove_vehicle(self, vehicle):
        """
        Remueve un vehículo del track
        """
        pass
    
    @abstractmethod
    def update_vehicles(self, dt):
        """
        Actualiza la posición de todos los vehículos en el track
        
        Args:
            dt: Delta time en segundos
            
        Returns:
            Lista de vehículos que completaron el track
        """
        pass
    
    @abstractmethod
    def update_vehicle_progress(self, vehicle, time_delta):
        """
        Actualiza el progreso de un solo vehículo por un delta de tiempo específico.
        Utilizado para aplicar el "tiempo sobrante" de un track anterior.

        Args:
            vehicle: La instancia del vehículo a mover.
            time_delta: El pequeño intervalo de tiempo a simular.
        """
        pass

    @abstractmethod
    def get_vehicle_position(self, vehicle):
        """
        Obtiene la posición 3D actual de un vehículo en el track
        
        Returns:
            Vector3 con la posición actual
        """
        pass
    
    @abstractmethod
    def get_vehicle_progress(self, vehicle):
        """
        Obtiene el progreso normalizado del vehículo (0 a 1)
        
        Returns:
            float entre 0.0 (inicio) y 1.0 (fin)
        """
        pass
    
    @abstractmethod
    def get_exit_position(self):
        """
        Obtiene la posición de salida del track (para transiciones)
        
        Returns:
            Vector3 con la posición de salida
        """
        pass
    
    @abstractmethod
    def get_exit_velocity(self, vehicle):
        """
        Obtiene la velocidad de salida del vehículo (para transiciones)
        
        Returns:
            Vector3 con la velocidad de salida
        """
        pass
    
    def get_vehicles(self):
        """
        Retorna lista de vehículos en el track
        """
        return [vehicle for vehicle, _ in self.vehicles.values()]
    
    def get_direction_vector(self):
        """
        Calcula el vector dirección normalizado del track
        """
        direction = self.end_pos - self.start_pos
        return direction.normalize() if direction.length() > 0 else Vector3(0, 0, 0)
    
    def calculate_position_at_progress(self, progress):
        """
        Calcula la posición 3D en un progreso específico del track
        
        Args:
            progress: Progreso normalizado (0 a 1)
            
        Returns:
            Vector3 con la posición interpolada
        """
        # Interpolación lineal entre start_pos y end_pos
        return self.start_pos + (self.end_pos - self.start_pos) * progress
    
    def is_vehicle_completed(self, progress):
        """
        Determina si un vehículo ha completado el track basado en su progreso
        """
        return progress >= 1.0
    
    def get_track_type(self):
        """
        Retorna el tipo de track para identificación
        """
        return self.__class__.__name__
    
    def get_status(self):
        """
        Retorna el estado actual del track para debug/monitoreo
        """
        return {
            "track_id": self.track_id,
            "track_type": self.get_track_type(),
            "start_pos": self.start_pos.to_tuple(),
            "end_pos": self.end_pos.to_tuple(),
            "length": self.length,
            "vehicle_count": len(self.vehicles),
            "vehicles": [v.vehicle_id for v in self.get_vehicles()]
        }