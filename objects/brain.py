class Brain:                            # Cordina toda la operacion de transporte
    def __init__(self, network):
        self.network = network          # Red que controla
        self.vehicles = []              # Vehiculos que considera
        self.circular_position = 0      # Indice para seleccion circular de vehiculos, cola de la serpiente
    
    def assign_vehicle_to_route(self, vehicle, origin_station, destination_station):     # asigna ruta valia a un VM entre estacion de origen y de destino
        connector = self.network.find_route(origin_station.id, destination_station.id)
        if connector:
            vehicle.assign_route(connector, destination_station)
            return True
        return False
    
    # FUNCION CRITICA, SE LLAMA DESDE LA SIMULACION
    def update(self, dt):
        """Update the entire system"""
        self.network.update_vehicle_positions(dt)
        
        # Handle vehicle assignments, passenger transfers, etc.
        self.circular_position = (self.circular_position + 1) % len(self.vehicles)      # Esta funiocn no la estoy entendiendo tanto



#### Notas Clase ####
# 1.
# por si mismo no tiene mucha responsabilidad ya que lo maneja network
# 2.
# no se mucho que significa el circular_position
# 3.
# la asignacion de ruta no se si me gusta tanto, eso puede ser mas dinamico