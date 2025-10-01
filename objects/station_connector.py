from objects.base import Vector3
import math

class StationConnector:
    def __init__(self, id: int, origin_station, destination_station, length: float, shape: str = "straight"):
        self.id = id
        self.origin_station = origin_station
        self.destination_station = destination_station
        self.length = length
        self.shape = shape
        self.acceleration_trees = []
        self.vehicles = []
        self.network_velocity = 10.0
        
        print(f"🛣️  Conector {id} creado:")
        print(f"   Desde: Estación {origin_station.id} ({origin_station.position.x}, {origin_station.position.z})")
        print(f"   Hasta: Estación {destination_station.id} ({destination_station.position.x}, {destination_station.position.z})")
        print(f"   Longitud: {length}m")
    
    def update_vehicle_movement(self, vehicle, dt):
        if self.acceleration_trees:
            return self._move_with_trees(vehicle, dt)
        else:
            return self._move_constant_velocity(vehicle, dt)

    def _move_constant_velocity(self, vehicle, dt):
        # DEBUG antes
        debug_before = f"VM {vehicle.id} en conector {self.id}: "
        debug_before += f"Pos=({vehicle.position.x:.1f},{vehicle.position.z:.1f}) "
        debug_before += f"Dist={vehicle.distance_traveled_on_tree:.1f}/{self.length:.1f}"
        print(debug_before)
        
        distance = self.network_velocity * dt
        vehicle.distance_traveled_on_tree += distance
        
        # Calcular progreso basado en la distancia recorrida
        progress = min(vehicle.distance_traveled_on_tree / self.length, 1.0)
        
        # Calcular posición usando interpolación lineal desde la posición ACTUAL
        # en lugar de desde el inicio fijo del conector
        direction_x = self.destination_station.position.x - self.origin_station.position.x
        direction_z = self.destination_station.position.z - self.origin_station.position.z
        
        # Normalizar dirección
        dir_length = math.sqrt(direction_x**2 + direction_z**2)
        if dir_length > 0:
            direction_x /= dir_length
            direction_z /= dir_length
        
        # Mover en la dirección del conector desde la posición actual
        move_x = direction_x * distance
        move_z = direction_z * distance
        
        vehicle.position.x += move_x
        vehicle.position.z += move_z
        
        vehicle.velocity = self.network_velocity
        
        # DEBUG después
        debug_after = f"  -> Movimiento: +{distance:.2f}m, "
        debug_after += f"Nueva Pos=({vehicle.position.x:.1f},{vehicle.position.z:.1f}) "
        debug_after += f"Progreso={progress:.2f}"
        print(debug_after)
        
        completed = vehicle.distance_traveled_on_tree >= self.length
        if completed:
            print(f"✅ VM {vehicle.id} COMPLETÓ conector {self.id}")
        
        return completed   
    
    def _move_with_trees(self, vehicle, dt):
        for tree in self.acceleration_trees:
            if not tree.execute_movement(vehicle, dt):
                return False
        return True