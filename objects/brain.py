class Brain:
    """
    CEREBRO CENTRAL DEL SISTEMA DE TRANSPORTE
    
    Responsabilidades:
    - Coordinar movimientos entre todos los componentes del sistema
    - Fiscalizar y validar el estado global de la simulación
    - Asignar rutas y destinos a los vehículos modulares (VMs)
    - Gestionar transiciones entre tracks (StationConnector y AccelerationTree)
    - Procesar operaciones en estaciones (embarque/desembarque)
    
    NO se encarga de:
    - Control del tiempo de simulación (lo maneja Simulation.py)
    - Configuración inicial del sistema
    - Visualización 3D o interfaz de usuario
    - Gestión de cámara o controles de vista
    
    Flujo principal:
    1. Simulation.py llama brain.update(dt) cada frame
    2. Brain actualiza network y procesa transiciones
    3. Brain coordina movimientos entre tracks
    4. Brain fiscaliza que todo esté sincronizado
    """
     
    def __init__(self, network):
        self.network = network
        self.vehicles = {}  # vehicle_id -> ModularVehicle
        self.stations = {}  # station_id -> Station
        self.simulation_time = 0.0
        
    def add_vehicle(self, vehicle):
        """Agrega un vehículo al sistema"""
        self.vehicles[vehicle.vehicle_id] = vehicle
        
    def add_station(self, station):
        """Agrega una estación al sistema"""
        self.stations[station.station_id] = station
        
    def assign_vehicle_to_route(self, vehicle, from_station, to_station):
        """
        Asigna una ruta completa a un vehículo
        Retorna: True si se pudo asignar la ruta
        """
        if from_station.station_id not in self.stations:
            return False
            
        # Asignar destino al vehículo
        vehicle.destination_station = to_station.station_id
        
        # Encontrar los acceleration trees objetivo
        target_trees = self._find_target_acceleration_trees(to_station.station_id)
        vehicle.target_acceleration_trees = target_trees
        
        # Posicionar vehículo en la estación de origen
        vehicle.current_station = from_station.station_id
        vehicle.state = "docked"
        from_station.docked_vehicles.append(vehicle)
        
        return True
        
    def _find_target_acceleration_trees(self, destination_station_id):
        """
        Encuentra los acceleration trees que llevan a la estación destino
        """
        station = self.stations.get(destination_station_id)
        if not station:
            return []
            
        return [tree.track_id for tree in station.arrival_trees]
    
    def update(self, dt):
        """
        Actualiza el estado del sistema por un paso de tiempo
        dt: delta time en segundos
        """
        self.simulation_time += dt
        
        # 1. Actualizar movimiento en la red
        self.network.update_vehicles(dt)
        
        # 2. Procesar transiciones entre tracks
        self._handle_track_transitions()
        
        # 3. Procesar operaciones en estaciones
        for station in self.stations.values():
            self._process_station_operations(station)
    
    def _handle_track_transitions(self):
        """Maneja las transiciones de vehículos entre tracks"""
        # Esta lógica se implementará cuando tengamos la clase Network
        pass
        
    def _process_station_operations(self, station):
        """Procesa embarque/desembarque en estaciones"""
        # Por ahora solo movemos vehículos de docked a departure trees
        vehicles_to_depart = []
        
        for vehicle in station.docked_vehicles:
            if vehicle.destination_station and vehicle.state == "docked":
                vehicles_to_depart.append(vehicle)
        
        for vehicle in vehicles_to_depart:
            self._depart_vehicle(vehicle, station)
    
    def _depart_vehicle(self, vehicle, station):
        """Envía un vehículo desde la estación"""
        if not station.departure_trees:
            return
            
        # Tomar el primer árbol de salida disponible
        departure_tree = station.departure_trees[0]
        
        # Transicionar vehículo
        station.docked_vehicles.remove(vehicle)
        departure_tree.add_vehicle(vehicle)
        vehicle.current_track = departure_tree
        vehicle.state = "accelerating_down"
        
    def get_system_status(self):
        """Retorna el estado actual del sistema para debug"""
        status = {
            "simulation_time": self.simulation_time,
            "total_vehicles": len(self.vehicles),
            "vehicles_by_state": {},
            "stations": len(self.stations)
        }
        
        # Contar vehículos por estado
        for vehicle in self.vehicles.values():
            state = vehicle.state
            status["vehicles_by_state"][state] = status["vehicles_by_state"].get(state, 0) + 1
            
        return status