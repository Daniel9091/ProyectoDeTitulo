from objects.acceleration_tree import AccelerationTree

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
        Actualiza el movimiento de todos los vehículos en la red con manejo de errores
        """
        vehicles_to_transfer = []
        
        try:
            # 1. Actualizar movimiento en cada track
            for track_id, track in list(self.tracks.items()):  # Usar list() para evitar modificación durante iteración
                try:
                    finished_vehicles = track.update_vehicles(dt)
                    for vehicle in finished_vehicles:
                        vehicles_to_transfer.append((vehicle, track_id))
                except Exception as e:
                    print(f"ERROR actualizando track {track_id}: {e}")
                    continue
            
            # 2. Procesar transiciones
            for vehicle, current_track_id in vehicles_to_transfer:
                try:
                    self._transfer_vehicle(vehicle, current_track_id)
                except Exception as e:
                    print(f"ERROR transfiriendo vehículo {vehicle.vehicle_id}: {e}")
                    continue
                    
        except Exception as e:
            print(f"ERROR crítico en Network.update_vehicles: {e}")
    
    def _transfer_vehicle(self, vehicle, current_track_id):
        """
        Transfiere un vehículo del track actual al siguiente con validaciones
        """
        # VALIDACIÓN 1: Verificar que el track actual existe
        if current_track_id not in self.tracks:
            print(f"ERROR: Track actual {current_track_id} no encontrado en la red")
            return
        
        current_track = self.tracks[current_track_id]
        possible_next_tracks = self.adjacency.get(current_track_id, [])
        
        if not possible_next_tracks:
            # Llegó al final del camino - debería estar en un acceleration tree de subida
            if isinstance(current_track, AccelerationTree) and current_track.direction == "up":
                # Llegó a una estación
                self._arrive_at_station(vehicle, current_track)
            else:
                print(f"WARNING: Vehículo {vehicle.vehicle_id} llegó al final sin estación")
            return
        
        # Buscar el mejor track siguiente
        next_track_id = self._choose_next_track(vehicle, possible_next_tracks)
        
        # VALIDACIÓN 2: Verificar que se encontró un track siguiente
        if not next_track_id:
            print(f"ERROR: No se pudo encontrar track siguiente para vehículo {vehicle.vehicle_id}")
            return
        
        # VALIDACIÓN 3: Verificar que el track siguiente existe
        if next_track_id not in self.tracks:
            print(f"ERROR: Track siguiente {next_track_id} no encontrado en la red")
            return
        
        next_track = self.tracks[next_track_id]
        
        try:
            # Remover del track actual
            current_track.remove_vehicle(vehicle)
            
            # Obtener posición y velocidad de salida para transición suave
            exit_position = current_track.get_exit_position()
            
            # **CORRECCIÓN CRÍTICA**: Obtener la velocidad como magnitud escalar, no como Vector3
            if hasattr(current_track, 'get_exit_velocity'):
                exit_velocity = current_track.get_exit_velocity(vehicle)
                # Si es Vector3, obtener solo la magnitud
                if hasattr(exit_velocity, 'length'):
                    exit_velocity_magnitude = exit_velocity.length()
                else:
                    exit_velocity_magnitude = exit_velocity
            else:
                exit_velocity_magnitude = 20.0  # Velocidad por defecto
            
            # Agregar al siguiente track con la posición y velocidad correctas
            next_track.add_vehicle(vehicle, exit_velocity_magnitude)
            vehicle.current_track = next_track
            
            # Actualizar estado del vehículo según el tipo de track
            if isinstance(next_track, AccelerationTree):
                if next_track.direction == "down":
                    vehicle.state = "accelerating_down"
                else:
                    vehicle.state = "accelerating_up"
            else:
                vehicle.state = "moving"
                
            print(f"Vehículo {vehicle.vehicle_id} transferido de {current_track_id} a {next_track_id}")
            
        except Exception as e:
            print(f"ERROR en transferencia de vehículo {vehicle.vehicle_id}: {e}")
            import traceback
            traceback.print_exc()

    def _choose_next_track(self, vehicle, possible_track_ids):
        """
        Elige el mejor track siguiente para un vehículo con validaciones
        """
        # DEBUG MEJORADO
        print(f"🚗 NAVEGACIÓN VM{vehicle.vehicle_id}:")
        print(f"   Destino: Estación {vehicle.destination_station}")
        print(f"   Target Trees: {vehicle.target_acceleration_trees}")
        print(f"   Opciones disponibles: {possible_track_ids}")
        
        # FILTRAR solo tracks que existen realmente
        valid_track_ids = [track_id for track_id in possible_track_ids 
                        if track_id in self.tracks]
        
        print(f"   Opciones válidas: {valid_track_ids}")
        
        if not valid_track_ids:
            print(f"❌ ERROR: No hay tracks válidos desde la posición actual")
            return None
        
        # VERIFICACIÓN CRÍTICA: Targets directos disponibles
        direct_targets = [t for t in valid_track_ids if t in vehicle.target_acceleration_trees]
        print(f"   Targets directos disponibles: {direct_targets}")
        
        # PRIORIDAD 1: Si el vehículo tiene destino específico, buscar árboles de subida
        if vehicle.destination_station:
            # Buscar árboles de subida que lleven a la estación destino
            up_trees = [t for t in valid_track_ids 
                    if self.tracks[t].get_track_type() == "AccelerationTree" 
                    and self.tracks[t].direction == "up"
                    and self.tracks[t].get_station_id() == vehicle.destination_station]
            
            if up_trees:
                # Verificar distancia segura en cada árbol
                for tree_id in up_trees:
                    tree = self.tracks[tree_id]
                    if self._check_safe_distance_in_tree(vehicle, tree):
                        chosen = tree_id
                        print(f"🎯 TOMANDO ÁRBOL DE SUBIDA: {chosen}")
                        return chosen
                
                # Si ningún árbol tiene distancia segura, tomar el primero disponible
                if up_trees:
                    chosen = up_trees[0]
                    print(f"⚠️  Tomando árbol de subida {chosen} sin verificación de distancia")
                    return chosen



        # PRIORIDAD 1: Si el vehículo no tiene destino específico, tomar el primero
        if not vehicle.target_acceleration_trees:
            chosen = valid_track_ids[0]
            print(f"🔄 SIN DESTINO: Tomando primer track {chosen}")
            return chosen
        
        # PRIORIDAD 2: Targets directos 
        if direct_targets:
            chosen = direct_targets[0]
            print(f"🎯 TOMANDO TARGET DIRECTO: {chosen}")
            return chosen
        
        # PRIORIDAD 3: Buscar tracks que lleven a los acceleration trees objetivo
        for track_id in valid_track_ids:
            if self._leads_to_target(track_id, vehicle.target_acceleration_trees):
                print(f"🔄 TOMANDO RUTA AL TARGET: {track_id}")
                return track_id
        
        # PRIORIDAD 4: Si no encuentra uno que lleve al objetivo, tomar el primero disponible
        chosen = valid_track_ids[0]
        print(f"⚠️  SIN RUTA AL TARGET: Tomando primer disponible {chosen}")
        return chosen

    def _check_safe_distance_in_tree(self, vehicle, tree):
        """Verifica distancia segura en un árbol específico"""
        for other_vehicle_id, vehicle_data in tree.vehicles.items():
            if other_vehicle_id != vehicle.vehicle_id:
                other_progress = vehicle_data['progress']
                # Distancia mínima reducida
                if other_progress > 0.9:  # Si está cerca del final, permitir entrada
                    continue
                if abs(other_progress - 0.5) < 0.3:  # Zona crítica del árbol
                    return False
        return True

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