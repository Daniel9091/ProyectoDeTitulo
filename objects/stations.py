from objects.base import Vector3

class Station:
    def __init__(self, id: int, name: str, position: Vector3):                              # Iniciacion de una estacion
        self.id = id                        # Identificador unico
        self.name = name                    # Nobre de la estacion
        self.position = position            # Cordenadas (x,y,z) de donde esta la estacion
        self.lanes = []                     # Lista de carriles por estacion (por ahora van a ser simpre 1 por simplificacion)
        self.passengers_waiting = []        # Lista de pasajeros que esperan en la estacion

        # NUEVO: Árboles de aceleración (salida) y desaceleración (entrada)
        self.acceleration_trees = []  # Para salir de la estación
        self.deceleration_trees = []  # Para entrar a la estación

    def add_acceleration_tree(self, tree):
        """Añade árbol de aceleración (salida)"""
        self.acceleration_trees.append(tree)
    
    def add_deceleration_tree(self, tree):
        """Añade árbol de desaceleración (entrada)"""
        self.deceleration_trees.append(tree)
    
    def get_acceleration_tree(self):
        """Obtiene un árbol de aceleración disponible"""
        return self.acceleration_trees[0] if self.acceleration_trees else None
    
    def get_deceleration_tree(self):
        """Obtiene un árbol de desaceleración disponible"""
        return self.deceleration_trees[0] if self.deceleration_trees else None


    def assign_lane(self, passenger):                                                       # Asignacion del pasajero al carril (implementacion simple)
        for lane in self.lanes:
            if lane.direction == "exit" and len(lane.vehicles) > 0:
                return lane
        return None
    
    def request_vehicle(self):                                                              # solicita vm a la via general en caso de nesesidad
        pass
    
    def process_arrival(self, vehicle):                                                     # Prosesa la llegada de un VM a la estacion (pasajeros bajen, acutalizar estado de VM)
        for passenger in vehicle.passengers[:]:
            if passenger.destination_station_id == self.id:                                 # copia de la lista para modificar
                passenger.exit_vehicle()                                                    # pasagero se baja del VM
                vehicle.remove_passenger(passenger)                                         # Pasagero eliminado del interior del VM



#### Notas de la clase ####

# 1.
# La funicon request_vehicle todavia no esta implementada pero est funcion solicita VM
# Atraves del brain al network, si es que detecta que tiene personas esperando en la estacion

# 2.
# Esta funcion se va a ir complejisando con el detalle que se le agrege:
# - como se mueven las personas al inerior (las filas que se hacen)
# - Debe prosesar la entrada y la salida de los pasageros de un VM
# - Etc.
