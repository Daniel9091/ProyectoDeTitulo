import math
from objects.base import Vector3

class AccelerationTree:
    def __init__(self, id: int, tree_type: str, start_position: Vector3, end_position: Vector3):
        self.id = id
        self.type = tree_type  # "acceleration", "deceleration", or "constant"
        self.start_position = start_position
        self.end_position = end_position
        
        # Calcular longitud y pendiente automáticamente
        dx = end_position.x - start_position.x
        dz = end_position.z - start_position.z
        self.length = math.sqrt(dx**2 + dz**2)
        
        # Calcular pendiente en grados
        if self.length > 0:
            self.slope = math.degrees(math.atan2(end_position.z - start_position.z, dx))
        else:
            self.slope = 0
    
    def execute_movement(self, vehicle, dt):
        """Ejecuta movimiento a lo largo del árbol usando interpolación lineal"""
        if vehicle.distance_traveled_on_tree >= self.length:
            return True  # Ábol completado
        
        # Calcular progreso (0 a 1)
        progress = vehicle.distance_traveled_on_tree / self.length
        
        # Interpolar posición entre start y end
        vehicle.position.x = self.start_position.x + progress * (self.end_position.x - self.start_position.x)
        vehicle.position.z = self.start_position.z + progress * (self.end_position.z - self.start_position.z)
        
        # Calcular velocidad según tipo
        if self.type == "acceleration":
            vehicle.velocity = min(15.0, 5.0 + progress * 10.0)  # Acelera de 5 a 15 m/s
        elif self.type == "deceleration":
            vehicle.velocity = max(0.0, 15.0 - progress * 10.0)  # Desacelera de 15 a 5 m/s
        else:  # constant
            vehicle.velocity = 10.0
        
        # Avanzar distancia
        distance = vehicle.velocity * dt
        vehicle.distance_traveled_on_tree += distance
        
        # DEBUG
        if vehicle.distance_traveled_on_tree >= self.length:
            print(f"DEBUG: VM {vehicle.id} completó árbol {self.id} ({self.type})")
        
        return vehicle.distance_traveled_on_tree >= self.length