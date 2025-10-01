import math
from objects.base import Vector3

class AccelerationTree:
    def __init__(self, id: int, tree_type: str, start_position: Vector3, end_position: Vector3):
        self.id = id
        self.type = tree_type
        self.start_position = start_position
        self.end_position = end_position
        
        # Calcular longitud y pendiente
        dx = end_position.x - start_position.x
        dz = end_position.z - start_position.z
        self.length = math.sqrt(dx**2 + dz**2)
        
        if self.length > 0:
            self.slope = math.degrees(math.atan2(dz, dx))
        else:
            self.slope = 0
        
        print(f"🌳 Árbol {id} creado:")
        print(f"   Tipo: {tree_type}")
        print(f"   Inicio: ({start_position.x}, {start_position.z})")
        print(f"   Fin: ({end_position.x}, {end_position.z})")
        print(f"   Longitud: {self.length:.1f}m")
        print(f"   Pendiente: {self.slope:.1f}°")
    
    def execute_movement(self, vehicle, dt):
        if vehicle.distance_traveled_on_tree >= self.length:
            return True
        
        # DEBUG: Información antes del movimiento
        debug_before = f"VM {vehicle.id} en árbol {self.id}({self.type}): "
        debug_before += f"Pos=({vehicle.position.x:.1f},{vehicle.position.z:.1f}) "
        debug_before += f"Dist={vehicle.distance_traveled_on_tree:.1f}/{self.length:.1f} "
        debug_before += f"Vel={vehicle.velocity:.1f}m/s"
        print(debug_before)
        
        # Calcular progreso
        progress = vehicle.distance_traveled_on_tree / self.length
        
        # Interpolar posición
        vehicle.position.x = self.start_position.x + progress * (self.end_position.x - self.start_position.x)
        vehicle.position.z = self.start_position.z + progress * (self.end_position.z - self.start_position.z)
        
        # Calcular velocidad según tipo (CORREGIDO)
        if self.type == "acceleration":
            # Debería bajar: velocidad aumenta
            vehicle.velocity = 5.0 + progress * 10.0  # 5 → 15 m/s
        elif self.type == "deceleration":
            # Debería subir: velocidad disminuye  
            vehicle.velocity = 15.0 - progress * 10.0  # 15 → 5 m/s
        else:
            vehicle.velocity = 10.0
        
        # Avanzar distancia (CORREGIDO: usar dt real)
        distance = vehicle.velocity * dt
        vehicle.distance_traveled_on_tree += distance
        
        # DEBUG: Información después del movimiento
        debug_after = f"  -> Movimiento: +{distance:.2f}m, "
        debug_after += f"Nueva Pos=({vehicle.position.x:.1f},{vehicle.position.z:.1f}) "
        debug_after += f"Nueva Vel={vehicle.velocity:.1f}m/s"
        print(debug_after)
        
        completed = vehicle.distance_traveled_on_tree >= self.length
        if completed:
            print(f"✅ VM {vehicle.id} COMPLETÓ árbol {self.id}({self.type})")
            print(f"   Posición final: ({vehicle.position.x:.1f}, {vehicle.position.z:.1f})")
        
        return completed