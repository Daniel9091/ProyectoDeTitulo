class Network:
    def __init__(self):                                                 # inicialisador de la clase
        self.connectors = []                                            # conectores en la red
        self.constant_velocity = 10.0                                   # Velocidad de la red subterranea 10 m/s (debe ser estandar)
        self.vehicles = []                                              # Vehiculos en la red
    
    def add_connector(self, connector):                                 # añade un conector a la red
        self.connectors.append(connector)
    
    def find_route(self, origin_station_id, destination_station_id):    # Encuentra ruta para los vm que comienzan su trayecto (simple)
        for connector in self.connectors:
            if (connector.origin_station.id == origin_station_id and 
                connector.destination_station.id == destination_station_id):
                return connector
        return None
    
    # (FUNCION CRITICA QUE SE LLAMA DESDE BRAIN)
    def update_vehicle_positions(self, dt):                             # Actualiza las posiciones de todos los VM
        for vehicle in self.vehicles:
            if vehicle.current_connector:
                connector_completed = vehicle.current_connector.update_vehicle_movement(vehicle, dt)
                if connector_completed:
                    vehicle.arrive_at_station()


#### Notas de la clase #####

# 1.
# creo que es una inconsitencia tener lista de los conectores y lista de vm por que los vm van a estar en los conectores
# pero la red nesesita saber los conectores que tiene
# considere que el vm sabe en que tramo va
# puede darse que esta inconsistencia sirva para las consultas futuras
