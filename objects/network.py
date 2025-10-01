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
    def update_vehicle_movements(self, dt):                             # Actualiza movimiento de cada VM en su conector actual
        completed_vehicles = []
        
        for vehicle in self.vehicles:
            if vehicle.current_connector:
                # Delegar movimiento al conector actual
                connector_completed = vehicle.current_connector.update_vehicle_movement(vehicle, dt)
                if connector_completed:
                    completed_vehicles.append(vehicle)
        
        # Retornar lista de VMs que completaron sus conectores
        return completed_vehicles

#### Notas de la clase #####

# 1.
# creo que es una inconsitencia tener lista de los conectores y lista de vm por que los vm van a estar en los conectores
# pero la red nesesita saber los conectores que tiene
# considere que el vm sabe en que tramo va
# puede darse que esta inconsistencia sirva para las consultas futuras



### Responsabilidades de la clase ###
