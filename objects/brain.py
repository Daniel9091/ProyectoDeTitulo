class Brain:                                        # Cordina toda la operacion de transporte
    def __init__(self, network):
        self.network = network                      # Red que controla
        self.vehicles = []                          # Vehiculos que considera
        self.circular_position = 0                  # Indice para seleccion circular de vehiculos, cola de la serpiente

        self.connectors = network.connectors
        self.pending_transitions = []

    def add_vehicle(self, vehicle):                 # Añadir Vms al sistema
        self.vehicles.append(vehicle)
        self.network.vehicles.append(vehicle)

    def assign_vehicle_to_route(self, vehicle, origin_station, destination_station):     # asigna ruta valia a un VM entre estacion de origen y de destino
        connector = self.network.find_route(origin_station.id, destination_station.id)
        if connector:
            vehicle.assign_route(connector, destination_station)
            return True
        return False
    
    # FUNCION CRITICA, SE LLAMA DESDE LA SIMULACION
    def update(self, dt):                           # Update teh etrie system
        # 1. Network actualiza posiciones y retorna VMs que completaron
        completed_vehicles = self.network.update_vehicle_movements(dt)
        
        # 2. Procesar VMs que completaron sus conectores
        for vehicle in completed_vehicles:
            self._handle_connector_completion(vehicle)

    def _process_transitions(self):                 # Maneja los Vms que terminaron su conetor actual
        for vehicle in self.vehicles:
            if vehicle.current_connector and self._is_connector_completed(vehicle):
                self._handle_connector_completion(vehicle)

    def _is_connector_completed(self, vehicle):     # Verifica si un VM completó su conector actual
        return vehicle.distance_traveled_on_tree >= vehicle.current_connector.length

    def _handle_connector_completion(self, vehicle):                # Maneja cuando un VM termina un conector
        current_connector = vehicle.current_connector
        current_station = current_connector.destination_station
        
        # Limpiar del conector actual
        if vehicle in current_connector.vehicles:
            current_connector.vehicles.remove(vehicle)
        
        # Lógica simple: si es la estación destino, llega
        if current_station.id == vehicle.destination_station.id:
            vehicle.arrive_at_station()
        else:
            # Buscar siguiente conector hacia el destino
            next_connector = self.network.find_route(
                current_station.id, 
                vehicle.destination_station.id
            )
            if next_connector:
                self._assign_vehicle_to_connector(vehicle, next_connector)
            else:
                # No hay ruta, llega forzadamente
                vehicle.arrive_at_station()
    
    def _assign_vehicle_to_connector(self, vehicle, connector):     # Asigna un VM a un conector espesifico 
        vehicle.current_connector = connector
        vehicle.distance_traveled_on_tree = 0.0
        connector.vehicles.append(vehicle)


#### Notas Clase ####
# 1.
# por si mismo no tiene mucha responsabilidad ya que lo maneja network
# 2.
# no se mucho que significa el circular_position
# 3.
# la asignacion de ruta no se si me gusta tanto, eso puede ser mas dinamico


### Responsabilidades de la clase ###