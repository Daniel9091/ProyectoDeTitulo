class Network:
    """
    RED COMPLETA DE VÍAS DEL SISTEMA
    
    Responsabilidades:
    - Almacenar y gestionar la topología completa de tracks
    - Manejar conexiones entre diferentes tipos de vías
    - Delegar movimiento a cada track individual
    - Administrar transiciones entre tracks
    - Proporcionar información de rutas y conexiones
    
    Estructura:
    - tracks: Diccionario de todos los tramos (StationConnector + AccelerationTree)
    - adjacency: Grafo de conexiones entre tracks
    - entry_points/exit_points: Mapeo estaciones -> acceleration trees
    """
    
    def __init__(self):
        self.tracks = {}  # dict: track_id -> Track (StationConnector o AccelerationTree)
        self.adjacency = {}  # dict: track_id -> [next_possible_tracks]
        self.entry_points = {}  # station_id -> [acceleration_trees_salida]
        self.exit_points = {}   # station_id -> [acceleration_trees_entrada]
        self.vehicles_in_transit = {}  # track_id -> [vehicles]
        
    def add_track(self, track):
        """Agrega un track a la red"""
        self.tracks[track.track_id] = track
        self.adjacency[track.track_id] = []
        
        # Registrar en entry_points o exit_points según el tipo
        if isinstance(track, AccelerationTree):
            if track.direction == "down":  # Árbol de salida
                station_id = track.get_station_id()
                if station_id not in self.entry_points:
                    self.entry_points[station_id] = []
                self.entry_points[station_id].append(track.track_id)
            else:  # Árbol de entrada
                station_id = track.get_station_id()
                if station_id not in self.exit_points:
                    self.exit_points[station_id] = []
                self.exit_points[station_id].append(track.track_id)
    
    def connect_tracks(self, from_track_id, to_track_id):
        """Conecta dos tracks en la red"""
        if from_track_id in self.adjacency:
            self.adjacency[from_track_id].append(to_track_id)
        else:
            self.adjacency[from_track_id] = [to_track_id]
    
    def update_vehicles(self, dt):
        """
        Actualiza el movimiento de todos los vehículos en la red
        
        Flujo:
        1. Por cada track, actualizar posición de sus vehículos
        2. Detectar vehículos que terminaron su tramo
        3. Manejar transiciones al siguiente track
        """
        vehicles_to_transfer = []
        
        # 1. Actualizar movimiento en cada track
        for track_id, track in self.tracks.items():
            finished_vehicles = track.update_vehicles(dt)
            for vehicle in finished_vehicles:
                vehicles_to_transfer.append((vehicle, track_id))
        
        # 2. Procesar transiciones
        for vehicle, current_track_id in vehicles_to_transfer:
            self._transfer_vehicle(vehicle, current_track_id)
    
    def _transfer_vehicle(self, vehicle, current_track_id):
        """
        Transfiere un vehículo del track actual al siguiente
        
        Lógica de transición:
        - Si el vehicle.target_acceleration_trees está en los tracks siguientes → tomar ese
        - Si no, tomar el primer track disponible
        - Si no hay tracks siguientes → error (llegó a destino final)
        """
        possible_next_tracks = self.adjacency.get(current_track_id, [])
        
        if not possible_next_tracks:
            # Llegó al final del camino - debería estar en un acceleration tree de subida
            current_track = self.tracks[current_track_id]
            if isinstance(current_track, AccelerationTree) and current_track.direction == "up":
                # Llegó a una estación
                self._arrive_at_station(vehicle, current_track)
            return
        
        # Buscar el mejor track siguiente
        next_track_id = self._choose_next_track(vehicle, possible_next_tracks)
        if next_track_id:
            next_track = self.tracks[next_track_id]
            current_track = self.tracks[current_track_id]
            
            # Remover del track actual
            current_track.remove_vehicle(vehicle)
            
            # Agregar al siguiente track
            next_track.add_vehicle(vehicle, current_track.get_exit_position())
            vehicle.current_track = next_track
            
            # Actualizar estado del vehículo según el tipo de track
            if isinstance(next_track, AccelerationTree):
                if next_track.direction == "down":
                    vehicle.state = "accelerating_down"
                else:
                    vehicle.state = "accelerating_up"
            else:
                vehicle.state = "moving"
    
    def _choose_next_track(self, vehicle, possible_track_ids):
        """
        Elige el mejor track siguiente para un vehículo
        
        Prioridad:
        1. Tracks que llevan a los acceleration trees objetivo del VM
        2. Primer track disponible
        """
        if not vehicle.target_acceleration_trees:
            return possible_track_ids[0] if possible_track_ids else None
        
        # Buscar tracks que lleven a los acceleration trees objetivo
        for track_id in possible_track_ids:
            if self._leads_to_target(track_id, vehicle.target_acceleration_trees):
                return track_id
        
        # Si no encuentra, tomar el primero
        return possible_track_ids[0] if possible_track_ids else None
    
    def _leads_to_target(self, track_id, target_trees, visited=None):
        """
        Verifica recursivamente si un track lleva a alguno de los trees objetivo
        """
        if visited is None:
            visited = set()
        
        if track_id in visited:
            return False
        
        visited.add(track_id)
        
        # Si este track es uno de los objetivos
        if track_id in target_trees:
            return True
        
        # Verificar tracks siguientes
        for next_track_id in self.adjacency.get(track_id, []):
            if self._leads_to_target(next_track_id, target_trees, visited):
                return True
        
        return False
    
    def _arrive_at_station(self, vehicle, arrival_tree):
        """
        Maneja la llegada de un vehículo a una estación
        """
        station_id = arrival_tree.get_station_id()
        
        # Remover del track
        arrival_tree.remove_vehicle(vehicle)
        
        # Actualizar estado del vehículo
        vehicle.state = "docked"
        vehicle.current_station = station_id
        vehicle.destination_station = None  # Destino cumplido
        vehicle.target_acceleration_trees = []
        
        # Aquí se conectaría con Brain para notificar llegada
        print(f"Vehículo {vehicle.vehicle_id} llegó a estación {station_id}")
    
    def get_station_departure_trees(self, station_id):
        """Obtiene los árboles de salida de una estación"""
        return [self.tracks[track_id] for track_id in self.entry_points.get(station_id, [])]
    
    def get_station_arrival_trees(self, station_id):
        """Obtiene los árboles de llegada de una estación"""
        return [self.tracks[track_id] for track_id in self.exit_points.get(station_id, [])]
    
    def get_network_status(self):
        """Retorna el estado actual de la red"""
        status = {
            "total_tracks": len(self.tracks),
            "total_connections": sum(len(conn) for conn in self.adjacency.values()),
            "vehicles_in_transit": sum(len(track.get_vehicles()) for track in self.tracks.values()),
            "entry_points": len(self.entry_points),
            "exit_points": len(self.exit_points)
        }
        return status