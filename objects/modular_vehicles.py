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
        
        # NUEVO: Estados de segmentos y árboles
        self.current_state = "idle"  # "on_acceleration_tree", "on_connector", "on_deceleration_tree"
        self.acceleration_tree = None
        self.deceleration_tree = None
    
    def assign_route(self, connector, destination_station, acceleration_tree, deceleration_tree):
        """Asigna ruta completa con todos los segmentos"""
        self.current_connector = connector
        self.destination_station = destination_station
        self.acceleration_tree = acceleration_tree
        self.deceleration_tree = deceleration_tree
        self.state = "moving"
        self.current_state = "on_acceleration_tree"
        self.distance_traveled_on_tree = 0.0
        
        # Posicionar en el inicio del árbol de aceleración
        self.position = acceleration_tree.start_position
    
    def get_current_segment(self):
        """Obtiene el segmento actual según el estado"""
        if self.current_state == "on_acceleration_tree":
            return self.acceleration_tree
        elif self.current_state == "on_connector":
            return self.current_connector
        elif self.current_state == "on_deceleration_tree":
            return self.deceleration_tree
        return None
    
    def arrive_at_station(self):
        """Llegada a estación destino"""
        self.state = "alighting"
        self.velocity = 0.0
        self.current_connector = None
        self.current_state = "idle"
        
        if self.destination_station:
            self.destination_station.process_arrival(self)
            self.destination_station = None

#### Notas clase #####

# 1.
# no se el por que el atributo d distancia en el arbol de acelreacion

# 2.
# se deben revisar bien las responsabilidades de cada una de las clases
# para que no hallan problemas

# se deben revisar bien los atributos de las clases para que se ocupen bien