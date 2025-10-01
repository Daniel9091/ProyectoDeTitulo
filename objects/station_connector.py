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
        
        progress = min(vehicle.distance_traveled_on_tree / self.length, 1.0)
        
        start = self.origin_station.position
        end = self.destination_station.position
        
        vehicle.position.x = start.x + (end.x - start.x) * progress
        vehicle.position.y = start.y + (end.y - start.y) * progress  
        vehicle.position.z = start.z + (end.z - start.z) * progress
        
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