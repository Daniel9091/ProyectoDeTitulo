class Brain:
    def __init__(self, network):
        self.network = network
        self.vehicles = []
        self.connectors = network.connectors
    
    def add_vehicle(self, vehicle):
        self.vehicles.append(vehicle)
        self.network.vehicles.append(vehicle)
    
    def assign_vehicle_to_route(self, vehicle, origin_station, destination_station):
        """Asigna ruta completa: árbol_aceleración → conector → árbol_desaceleración"""
        # 1. Encontrar conector principal
        connector = self.network.find_route(origin_station.id, destination_station.id)
        if not connector:
            return False
        
        # 2. Obtener árboles de las estaciones
        acceleration_tree = origin_station.get_acceleration_tree()
        deceleration_tree = destination_station.get_deceleration_tree()
        
        if not acceleration_tree or not deceleration_tree:
            return False
        
        # 3. Asignar ruta completa al vehículo
        vehicle.assign_route(connector, destination_station, acceleration_tree, deceleration_tree)
        return True
    
    def update(self, dt):
        """Actualiza todo el sistema con nueva lógica de segmentos"""
        completed_vehicles = self.network.update_vehicle_movements(dt)
        
        for vehicle in completed_vehicles:
            self._handle_segment_completion(vehicle)
    
    def _handle_segment_completion(self, vehicle):
        """Maneja cuando un VM completa un segmento de su ruta"""
        current_state = vehicle.current_state
        
        if current_state == "on_acceleration_tree":
            # Terminó árbol de aceleración, pasar al conector
            print(f"DEBUG: VM {vehicle.id} pasando a conector")
            vehicle.current_state = "on_connector"
            vehicle.distance_traveled_on_tree = 0.0
            
        elif current_state == "on_connector":
            # Terminó conector, pasar a árbol de desaceleración
            print(f"DEBUG: VM {vehicle.id} pasando a árbol desaceleración")
            vehicle.current_state = "on_deceleration_tree"
            vehicle.distance_traveled_on_tree = 0.0
            
        elif current_state == "on_deceleration_tree":
            # Terminó árbol de desaceleración, llegar a estación
            print(f"DEBUG: VM {vehicle.id} llegando a estación")
            vehicle.arrive_at_station()


#### Notas Clase ####
# 1.
# por si mismo no tiene mucha responsabilidad ya que lo maneja network
# 2.
# no se mucho que significa el circular_position
# 3.
# la asignacion de ruta no se si me gusta tanto, eso puede ser mas dinamico


### Responsabilidades de la clase ###