from objects.base import Vector3

class ModularVehicle:
    def __init__(self, id: int, capacity: int, position: Vector3): # Inicialisador de un VM 
        self.id = id                            # Identificador unico
        self.capacity = capacity                # Capacidad del VM
        self.passengers = []                    # Pasajeros que tiene en el inteior
        self.velocity = 0.0                     # Velocidad VM en m/s
        self.state = "idle"                     # idle, moving, boarding, alighting
        self.position = position                # Posicion VM en el espacio
        self.destination_station = None         # Estacion de destino
        self.current_connector = None           # conector actual donde se esta moviendo
        self.distance_traveled_on_tree = 0.0    # distancia recorrida en el arbol de aceleracion actual
    
    def add_passenger(self, passenger):                     # agrega un pasajero al VM 
        if len(self.passengers) < self.capacity:
            self.passengers.append(passenger)
            return True
        return False
    
    def remove_passenger(self, passenger):                  # elimina un pasajero del VM 
        if passenger in self.passengers:
            self.passengers.remove(passenger)
            return True
        return False
    
    def assign_route(self, connector, destination_station): # se asigna una ruta al VM por donde debe moverse 
        self.current_connector = connector
        self.destination_station = destination_station
        self.state = "moving"
        self.distance_traveled_on_tree = 0.0
    
    def arrive_at_station(self):                            # maneja la llegada dle vehiculo a una estacion de destino 
        self.state = "alighting"                            # Cambia estado
        self.velocity = 0.0                                 # Detiene VM
        self.current_connector = None                       # Limpia referencia al conector acutal
        
        if self.destination_station:                        # Notifica a la estacion la llegada
            self.destination_station.process_arrival(self)
            self.destination_station = None


#### Notas clase #####

# 1.
# no se el por que el atributo d distancia en el arbol de acelreacion

# 2.
# se deben revisar bien las responsabilidades de cada una de las clases
# para que no hallan problemas

# se deben revisar bien los atributos de las clases para que se ocupen bien