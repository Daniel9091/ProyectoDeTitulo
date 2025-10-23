from objects.acceleration_tree import AccelerationTree

class Network:
    """
    RED COMPLETA DE VÍAS DEL SISTEMA
    
    Responsabilidades PRINCIPALES:
    - Almacenar y gestionar la topología completa de tracks
    - Manejar conexiones entre diferentes tipos de vías
    - Delegar movimiento a cada track individual
    - Administrar transiciones entre tracks
    - Proporcionar información de rutas y conexiones
    
    Responsabilidades NO incluidas:
    - Selección de árboles de aceleración (lo hace TreeSelector)
    - Toma de decisiones de routing complejas (solo sigue destinos)
    - Gestión de pasajeros (lo hace Station/Brain)
    """

    def __init__(self):
        self.tracks = {}  # dict: track_id -> Track (StationConnector o AccelerationTree)
        self.adjacency = {}  # dict: track_id -> [next_possible_tracks]
        self.entry_points = {}  # station_id -> [acceleration_trees_salida]
        self.exit_points = {}   # station_id -> [acceleration_trees_entrada]
        self.vehicles_in_transit = {}  # track_id -> [vehicles]
        
        # ✅ NUEVO: TreeSelector inyectado (se configurará desde Simulation)
        self.tree_selector = None
        self.brain = None # Referencia al Brain para notificaciones

    # ========== MÉTODOS EXISTENTES (SIN CAMBIOS) ==========

    def add_track(self, track):
        """Agrega un track a la red (sin cambios)"""
        self.tracks[track.track_id] = track
        self.adjacency[track.track_id] = []
        
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
        """Conecta dos tracks en la red (sin cambios)"""
        if from_track_id in self.adjacency:
            self.adjacency[from_track_id].append(to_track_id)
        else:
            self.adjacency[from_track_id] = [to_track_id]

    def update_vehicles(self, dt):
        """Actualiza movimiento de vehículos (sin cambios)"""
        vehicles_to_transfer = []
        
        try:
            for track_id, track in list(self.tracks.items()):
                try:
                    finished_vehicles = track.update_vehicles(dt)
                    for vehicle in finished_vehicles:
                        vehicles_to_transfer.append((vehicle, track_id))
                except Exception as e:
                    print(f"ERROR: actualizando track {track_id}: {e}")
                    continue
            
            for vehicle, current_track_id in vehicles_to_transfer:
                try:
                    self._transfer_vehicle(vehicle, current_track_id)
                except Exception as e:
                    print(f"ERROR: transfiriendo vehículo {vehicle.vehicle_id}: {e}")
                    continue
                    
        except Exception as e:
            print(f"ERROR crítico en Network.update_vehicles: {e}")

    def _transfer_vehicle(self, vehicle, current_track_id):
        """Transfiere vehículo entre tracks"""

        if current_track_id not in self.tracks:
            print(f"ERROR: Track actual {current_track_id} no encontrado en la red")
            return
        
        current_track = self.tracks[current_track_id]
        possible_next_tracks = self.adjacency.get(current_track_id, [])
        
        # ✅ CORRECCIÓN: Si el vehículo acaba de terminar un árbol de llegada ('up'),
        # se considera que ha llegado a la estación, incluso si hay un track conectado después (como un andén).
        # Esto asegura que el destino se limpie y la demanda se cumpla.
        if isinstance(current_track, AccelerationTree) and current_track.direction == "up":
            # El método _arrive_at_station se encargará de remover el vehículo del track actual.
            self._arrive_at_station(vehicle, current_track)

        if not possible_next_tracks:
            if isinstance(current_track, AccelerationTree) and current_track.direction == "up":
                self._arrive_at_station(vehicle, current_track) # Brain se pasa aquí
            else:
                print(f"WARNING: Vehículo {vehicle.vehicle_id} llegó al final sin estación")
            return
        
        # Usar nueva lógica simplificada
        next_track_id = self._choose_next_track_simplified(vehicle, possible_next_tracks)
        
        if not next_track_id:
            print(f"ERROR: No se pudo encontrar track siguiente para vehículo {vehicle.vehicle_id}")
            return
        
        if next_track_id not in self.tracks:
            print(f"ERROR: Track siguiente {next_track_id} no encontrado en la red")
            return
        
        next_track = self.tracks[next_track_id]
        
        try:
            # Obtener la velocidad de salida del track actual
            if hasattr(current_track, 'get_exit_velocity'):
                exit_velocity = current_track.get_exit_velocity(vehicle)
                # Para StationConnectors, la velocidad ya es una magnitud.
                # Para AccelerationTrees, get_exit_velocity devuelve un vector, necesitamos la magnitud.
                exit_velocity_magnitude = exit_velocity.length() if hasattr(exit_velocity, 'length') else exit_velocity
            else:
                exit_velocity_magnitude = 20.0

            # Usar el método centralizado que también actualiza la velocidad del VM
            vehicle.transfer_to_track(next_track, entry_velocity=exit_velocity_magnitude)
            
        except Exception as e:
            print(f"ERROR en transferencia de vehículo {vehicle.vehicle_id}: {e}")
            import traceback
            traceback.print_exc()

    # ========== LÓGICA DE NAVEGACIÓN REFACTORIZADA ==========

    def _choose_next_track_simplified(self, vehicle, possible_track_ids):
        """
        LÓGICA SIMPLIFICADA DE ELECCIÓN DE TRACKS
        ✅ REEMPLAZA la función _choose_next_track original
        
        Args:
            vehicle: Vehículo que necesita elegir track
            possible_track_ids: Lista de tracks disponibles
            
        Returns:
            track_id: ID del track seleccionado
        """
        valid_tracks = [self.tracks[tid] for tid in possible_track_ids if tid in self.tracks]
        
        if not valid_tracks:
            print(f"ERROR: Navegacion VM{vehicle.vehicle_id}: No hay tracks válidos")
            return None

        # FILTRO 1: ¿Son árboles de subida hacia mi destino?
        target_arrival_trees = self._get_target_arrival_trees(vehicle, valid_tracks)
        if target_arrival_trees:
            # ✅ DELEGAR al TreeSelector la selección del mejor árbol
            best_tree = self.tree_selector.select_best_tree(
                target_arrival_trees, 
                vehicle, 
                strategy='progressive_saturation', # Mantener saturación progresiva como deseado
                station_id=vehicle.destination_station # Pasar station_id por si la estrategia lo necesita
            )

            if best_tree:
                print(f"🎯 NAVEGACIÓN VM{vehicle.vehicle_id}: Tomando árbol {best_tree.track_id}")
                return best_tree.track_id
            else:
                # Todos los árboles de llegada objetivo están saturados o no disponibles para este VM.
                destination_station_id = vehicle.destination_station # Guardar el destino antes de potencialmente borrarlo
                print(f"ADVERTENCIA: NAVEGACIÓN VM{vehicle.vehicle_id}: Todos los árboles de llegada a Estación {destination_station_id} saturados.")

                # Si el VM está vacío, se libera su destino y se reasigna la demanda.
                if vehicle.passengers == 0:
                    print(f"VM{vehicle.vehicle_id} está vacío y no puede acceder a Estación {destination_station_id}. Liberando destino y reasignando demanda.")
                    vehicle.clear_destination() # Borra el destino y los árboles objetivos del VM
                    # ✅ APLICAR PENALIZACIÓN
                    vehicle.apply_penalty(destination_station_id, self.brain.simulation_time)
                    if self.brain:
                        # Notificar al Brain que la demanda original para esta estación debe ser reasignada.
                        self.brain.reassign_failed_demand(destination_station_id)
                    # Después de liberar el destino, el vehículo ya no tiene un destino específico.
                    # La lógica continuará a los filtros 2 y 3, pero ahora el vehículo se considerará "sin destino".
                    # Esto hará que caiga en el FILTRO 3 (cualquier track disponible) para seguir moviéndose.

        # FILTRO 2: ¿Hay tracks que lleven a mi destino?
        destination_tracks = self._get_tracks_to_destination(vehicle, valid_tracks)
        if destination_tracks:
            chosen_track = destination_tracks[0]  # Tomar el primero
            return chosen_track.track_id

        # FILTRO 3: Flujo continuo - cualquier track disponible
        chosen_track = valid_tracks[0]
        return chosen_track.track_id

    def _get_target_arrival_trees(self, vehicle, valid_tracks):
        """
        Filtra árboles de subida que son objetivos directos del vehículo
        
        Args:
            vehicle: Vehículo con destino
            valid_tracks: Lista de tracks disponibles
            
        Returns:
            list: Árboles de subida que llevan al destino
        """
        if not vehicle.destination_station or not vehicle.target_acceleration_trees:
            return []
            
        target_trees = []
        for track in valid_tracks:
            if (isinstance(track, AccelerationTree) and 
                track.direction == "up" and
                track.track_id in vehicle.target_acceleration_trees):
                target_trees.append(track)
                
        return target_trees

    def _get_tracks_to_destination(self, vehicle, valid_tracks):
        """
        Encuentra tracks que eventualmente lleven al destino del vehículo
        
        Args:
            vehicle: Vehículo con destino
            valid_tracks: Lista de tracks disponibles
            
        Returns:
            list: Tracks que llevan al destino
        """
        if not vehicle.destination_station:
            return []
            
        destination_tracks = []
        for track in valid_tracks:
            if self._leads_to_destination(track.track_id, vehicle.destination_station):
                destination_tracks.append(track)
                
        return destination_tracks

    def _leads_to_destination(self, track_id, destination_station_id, visited=None):
        """
        Verifica recursivamente si un track lleva a la estación destino
        ✅ MANTENIDO de la versión original (funciona bien)
        """
        if visited is None:
            visited = set()
        
        if track_id in visited:
            return False
        
        visited.add(track_id)
        
        track = self.tracks.get(track_id)
        if not track:
            return False
        
        # Si es un árbol de subida y su estación es el destino
        if (isinstance(track, AccelerationTree) and 
            track.direction == "up" and 
            track.station_id == destination_station_id):
            return True
        
        # Verificar tracks siguientes recursivamente
        for next_track_id in self.adjacency.get(track_id, []):
            if self._leads_to_destination(next_track_id, destination_station_id, visited):
                return True
        
        return False

    # ========== MÉTODOS DE CONFIGURACIÓN Y MONITOREO ==========

    def set_tree_selector(self, tree_selector):
        """
        Configura el TreeSelector (inyección de dependencias)
        
        Args:
            tree_selector: Instancia de TreeSelector
        """
        self.tree_selector = tree_selector
        self.brain = tree_selector.brain # Asumimos que el selector puede tener una ref al brain

    def get_navigation_status(self):
        """
        Proporciona estado del sistema de navegación
        
        Returns:
            dict: Información de estado
        """
        if not self.tree_selector:
            return {"tree_selector": "No configurado"}
            
        # Obtener estado de todos los árboles de aceleración
        acceleration_trees = [t for t in self.tracks.values() 
                            if isinstance(t, AccelerationTree)]
        
        tree_status = self.tree_selector.get_trees_status(acceleration_trees)
        
        return {
            "tree_selector": "Configurado",
            "total_tracks": len(self.tracks),
            "acceleration_trees": len(acceleration_trees),
            "tree_occupancy": tree_status['overall_occupancy_rate'],
            "available_arrival_trees": tree_status['available_trees']
        }

    # ========== MÉTODOS EXISTENTES (SIN CAMBIOS) ==========

    def _arrive_at_station(self, vehicle, arrival_tree):
        """Maneja llegada a estación (sin cambios)"""
        station_id = arrival_tree.get_station_id()
        
        # El vehículo ya no se detiene, solo actualiza su estado.
        # La transferencia al siguiente track se maneja en _transfer_vehicle.
        arrival_tree.remove_vehicle(vehicle)
        # ✅ Pasa la referencia del Brain para que el vehículo pueda notificar la llegada.
        vehicle.arrive_at_station(station_id, self.brain)

    def get_station_departure_trees(self, station_id):
        """Obtiene árboles de salida (sin cambios)"""
        return [self.tracks[track_id] for track_id in self.entry_points.get(station_id, [])]

    def get_station_arrival_trees(self, station_id):
        """Obtiene árboles de llegada (sin cambios)"""
        return [self.tracks[track_id] for track_id in self.exit_points.get(station_id, [])]

    def get_network_status(self):
        """Retorna estado de la red (mejorado con info de navegación)"""
        status = {
            "total_tracks": len(self.tracks),
            "total_connections": sum(len(conn) for conn in self.adjacency.values()),
            "vehicles_in_transit": sum(len(track.get_vehicles()) for track in self.tracks.values()),
            "entry_points": len(self.entry_points),
            "exit_points": len(self.exit_points),
            "navigation_system": self.get_navigation_status()
        }
        return status