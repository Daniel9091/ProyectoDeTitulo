from objects.base import Vector3

class ModularVehicle:
    def __init__(self, id: int, capacity: int, position: Vector3):
        self.id = id
        self.capacity = capacity
        self.passengers = []
        self.velocity = 0.0
        self.state = "idle"
        self.position = position
        self.destination_station = None
        self.current_connector = None
        self.distance_traveled_on_tree = 0.0
        
        # Estados de segmentos y árboles
        self.current_state = "idle"
        self.acceleration_tree = None
        self.deceleration_tree = None
        
        # DEBUG: Historial de posiciones
        self.position_history = []
    
    def assign_route(self, connector, destination_station, acceleration_tree, deceleration_tree):
        self.current_connector = connector
        self.destination_station = destination_station
        self.acceleration_tree = acceleration_tree
        self.deceleration_tree = deceleration_tree
        self.state = "moving"
        self.current_state = "on_acceleration_tree"
        self.distance_traveled_on_tree = 0.0
        
        # Posicionar en el inicio del árbol de aceleración
        self.position = Vector3(acceleration_tree.start_position.x, 
                              acceleration_tree.start_position.y, 
                              acceleration_tree.start_position.z)
        
        print(f"🚀 VM {self.id} INICIA RUTA:")
        print(f"   Estado: {self.current_state}")
        print(f"   Posición inicial: ({self.position.x:.1f}, {self.position.y:.1f}, {self.position.z:.1f})")
        print(f"   Destino: Estación {destination_station.id}")
    
    def get_current_segment(self):
        if self.current_state == "on_acceleration_tree":
            return self.acceleration_tree
        elif self.current_state == "on_connector":
            return self.current_connector
        elif self.current_state == "on_deceleration_tree":
            return self.deceleration_tree
        return None
    
    def get_debug_info(self):
        segment = self.get_current_segment()
        segment_type = "None"
        if segment:
            if hasattr(segment, 'type'):
                segment_type = f"Tree_{segment.id}({segment.type})"
            else:
                segment_type = f"Connector_{segment.id}"
        
        return {
            'vm_id': self.id,
            'state': self.current_state,
            'position': (self.position.x, self.position.y, self.position.z),
            'velocity': self.velocity,
            'distance_traveled': self.distance_traveled_on_tree,
            'segment': segment_type
        }
    
    def arrive_at_station(self):
        print(f"🏁 VM {self.id} LLEGA A ESTACIÓN {self.destination_station.id}")
        self.state = "alighting"
        self.velocity = 0.0
        self.current_connector = None
        self.current_state = "idle"
        
        if self.destination_station:
            self.destination_station.process_arrival(self)
            self.destination_station = None