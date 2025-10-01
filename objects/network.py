class Network:
    def __init__(self):
        self.connectors = []
        self.constant_velocity = 10.0
        self.vehicles = []
    
    def add_connector(self, connector):
        self.connectors.append(connector)
    
    def find_route(self, origin_station_id, destination_station_id):
        for connector in self.connectors:
            if (connector.origin_station.id == origin_station_id and 
                connector.destination_station.id == destination_station_id):
                return connector
        return None
    
    def update_vehicle_movements(self, dt):
        """Actualiza movimiento según el segmento actual de cada VM"""
        completed_vehicles = []
        
        for vehicle in self.vehicles:
            if vehicle.state != "moving":
                continue
                
            current_segment = vehicle.get_current_segment()
            if not current_segment:
                continue
            
            # Delegar movimiento al segmento actual
            if hasattr(current_segment, 'update_vehicle_movement'):
                # Es un StationConnector
                segment_completed = current_segment.update_vehicle_movement(vehicle, dt)
            else:
                # Es un AccelerationTree
                segment_completed = current_segment.execute_movement(vehicle, dt)
            
            if segment_completed:
                completed_vehicles.append(vehicle)
        
        return completed_vehicles

#### Notas de la clase #####

# 1.
# creo que es una inconsitencia tener lista de los conectores y lista de vm por que los vm van a estar en los conectores
# pero la red nesesita saber los conectores que tiene
# considere que el vm sabe en que tramo va
# puede darse que esta inconsistencia sirva para las consultas futuras



### Responsabilidades de la clase ###
