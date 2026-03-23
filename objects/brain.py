from objects.acceleration_tree import AccelerationTree
from objects.boarding_lane import BoardingLane
from objects.spatial_grid import SpatialGrid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from objects.passenger import Passenger
    from objects.stations import Station


class Brain:
    """
    CEREBRO CENTRAL DEL SISTEMA DE TRANSPORTE - COORDINADOR GLOBAL
    
    Responsabilidades PRINCIPALES:
    - Coordinar movimientos entre todos los componentes del sistema
    - Fiscalizar y validar el estado global de la simulación
    - Gestionar transiciones entre tracks y operaciones en estaciones
    - Procesar solicitudes de VMs desde múltiples estaciones
    - Monitorear el estado del sistema usando TreeSelector
    
    Responsabilidades NO incluidas:
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
        self.passengers: dict[str, 'Passenger'] = {} # ID -> Objeto Passenger
        
        # ✅ NUEVO: Sistema de gestión de solicitudes
        self.pending_requests = []  # Solicitudes de VMs pendientes
        self.request_cooldown = 2.0  # Segundos entre procesamiento de solicitudes
        self.last_request_process_time = 0.0

        # ✅ NUEVO: Sistema de Demanda Persistente
        self.station_demand = {}  # station_id -> número de vehículos solicitados
        self._demand_fulfillment_cooldown = 1.0 # Frecuencia para intentar satisfacer la demanda
        self._time_since_last_demand_check = 0.0
        
        # ✅ NUEVO: Sistema de optimización de colisiones
        self.collision_grid = SpatialGrid(cell_size=50.0) # Celdas de 50x50x50 metros

        # Lista para predicción de colisiones sincronizada
        self.pending_down_tree_entries = []

        # Parámetros de gestión de slots en tren continuo (configurados desde Simulation)
        self.slot_search_range = 10   # Slots a revisar antes/después ante colisión
        self.accel_range_min = 0.2    # Aceleración mínima permitida en árbol de bajada (m/s²)
        self.accel_range_max = 1.5    # Aceleración máxima permitida en árbol de bajada (m/s²)

        # Tren Continuo: se inyecta desde Simulation
        self.continuous_train = None
        self._train_exit_junctions = []  # [{belt_x, up_tree_ids}, ...]

        # ✅ NUEVO: Estadísticas y monitoreo
        self.stats = {
            'total_vehicle_assignments': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'collisions_prevented': 0,
            'emergency_flow_events': 0
        }
        
        print("🧠 Brain inicializado - Sistema de coordinación central listo")

    # ========== CONFIGURACIÓN INICIAL DEL SISTEMA ==========

    def add_vehicle(self, vehicle):
        """Agrega un vehículo al sistema (sin cambios)"""
        self.vehicles[vehicle.vehicle_id] = vehicle

    def add_station(self, station):
        """Agrega una estación al sistema (mejorado)"""
        self.stations[station.station_id] = station

    def register_new_passenger(self, passenger: 'Passenger'):
        """
        Registra un nuevo pasajero en el sistema central y lo asigna a su estación de origen.
        Llamado por el PassengerSpawnSystem.
        """
        if passenger.passenger_id in self.passengers:
            print(f"ADVERTENCIA: Pasajero {passenger.passenger_id} ya está registrado.")
            return

        # 1. Registrar en el cerebro
        self.passengers[passenger.passenger_id] = passenger
        
        # 2. Encontrar la estación de origen
        origin_station = self.stations.get(passenger.origin_station_id)
        
        if not origin_station:
            print(f"ERROR: No se encontró la estación de origen {passenger.origin_station_id} para el pasajero {passenger.passenger_id}")
            passenger.state = "ARRIVED" # Marcar como inválido
            return
            
        # 3. Entregar el pasajero a la estación para que lo gestione
        origin_station.add_passenger_to_entrance_queue(passenger)

    def assign_vehicle_to_route(self, vehicle, from_station, to_station):
        """
        Asigna una ruta completa a un vehículo
        MEJORADO: Usa TreeSelector para asignación óptima de árboles
        """
        # if from_station.station_id not in self.stations:
        #     print(f"ERROR: Estación origen {from_station.station_id} no registrada")
        #     return False
            
        # Verificar capacidad de la estación destino
        # if not to_station.has_arrival_capacity():
        #     print(f"ERROR: Estación destino {to_station.name} no tiene capacidad")
        #     return False

        # Asignar destino al vehículo
        vehicle.destination_station = to_station.station_id
        
        # Usar TreeSelector para encontrar árboles objetivo óptimos
        target_trees = self._find_optimal_target_trees(to_station.station_id, vehicle)
        vehicle.target_acceleration_trees = target_trees

        # DEBUG: Imprimir información de ruta
        # print(f"🧭 ASIGNACIÓN DE RUTA: Vehículo {vehicle.vehicle_id} desde {from_station.name} a {to_station.name}")
        # print(f"   Árboles objetivo: {target_trees}")
        
        # Posicionar vehículo en la estación de origen
        vehicle.current_station = from_station.station_id
        vehicle.state = "moving" # Los vehículos ya no se detienen
        
        # ✅ NUEVO: Actualizar estadísticas
        self.stats['total_vehicle_assignments'] += 1
        return True

    def _find_optimal_target_trees(self, destination_station_id, vehicle):
        """
        Encuentra los árboles objetivo óptimos usando TreeSelector
        ✅ NUEVO: Reemplaza la búsqueda simple por selección inteligente
        """
        station = self.stations.get(destination_station_id)
        if not station or not station.arrival_trees:
            return []
            
        # Si la estación tiene TreeSelector, usarlo para selección óptima
        if hasattr(station, 'tree_selector') and station.tree_selector:
            optimal_tree = station.select_optimal_arrival_tree(vehicle)
           
            return [tree.track_id for tree in station.arrival_trees]
        
        # Fallback: usar todos los árboles disponibles (comportamiento original)
        return [tree.track_id for tree in station.arrival_trees]

    # ========== ✅ NUEVO: GESTIÓN DE DEMANDA PERSISTENTE ==========

    def register_demand(self, station_id, count):
        """Una estación registra su necesidad de 'count' vehículos."""
        if station_id not in self.station_demand:
            self.station_demand[station_id] = 0
        self.station_demand[station_id] += count
        # print(f"🧠 Demanda registrada: Estación {station_id} necesita {count} VMs. Total pendiente: {self.station_demand[station_id]}")

    def fulfill_demand(self, station_id, count=1, assigned_not_arrived=False):
        """
        Marca una demanda como satisfecha (vehículo llegó) o asignada (vehículo en ruta).
        Si assigned_not_arrived es True, significa que un vehículo ha sido asignado,
        pero aún no ha llegado, por lo que se reduce la demanda pendiente en el Brain.
        """
        if station_id in self.station_demand:
            self.station_demand[station_id] = max(0, self.station_demand[station_id] - count)
            if assigned_not_arrived:
                # print(f"🧠 Demanda para Estación {station_id} reducida por asignación. Restante: {self.station_demand[station_id]}")
                pass

    def reassign_failed_demand(self, station_id):
        """Vuelve a registrar la demanda para una asignación que falló."""
        # print(f"🧠 Fallo de asignación para Estación {station_id}. Re-registrando demanda.")
        # No decrementamos la demanda actual, simplemente nos aseguramos de que se intente de nuevo.
        station = self.stations.get(station_id)
        if not station:
            print(f"ERROR: Estación {station_id} no encontrada para reasignación de demanda.")
            return

        # Intenta encontrar un vehículo disponible y asignarlo inmediatamente.
        # Esto también considerará el vehículo que acaba de ser rechazado y liberó su destino.
        vehicle_id = station.request_vehicle(self)
        if vehicle_id:
           pass
            # La llamada a station.request_vehicle ya maneja el decremento de station_demand si es exitosa.
        else:
            # Si no se pudo encontrar ningún vehículo, entonces re-registra la demanda para que se recoja más tarde.
            self.register_demand(station_id, 1)

    # ========== GESTIÓN DE SOLICITUDES DE VEHÍCULOS ==========

    def request_vehicle_for_station(self, station_id, destination_station_id=None):
        """
        SOLICITA UN VM PARA UNA ESTACIÓN ESPECÍFICA
        Sistema centralizado de gestión de solicitudes
        
        Args:
            station_id: Estación que solicita el VM
            destination_station_id: Destino final (opcional)
            
        Returns:
            str: ID del VM asignado, o None si no hay disponibles
        """
        station = self.stations.get(station_id)
        if not station:
            print(f"ERROR: Solicitud de Estación {station_id} no encontrada")
            return None
        
        # Agregar a la cola de solicitudes pendientes
        request = {
            'station_id': station_id,
            'destination_station_id': destination_station_id,
            'timestamp': self.simulation_time,
            'processed': False
        }
        
        self.pending_requests.append(request)
        
        # Procesar inmediatamente para respuesta rápida
        return self._process_single_request(request)

    def _process_single_request(self, request):
        """
        PROCESA UNA SOLA SOLICITUD DE VM
        Lógica de procesamiento individual
        """
        station = self.stations.get(request['station_id'])
        if not station:
            return None
        
        # Delegar a la estación la búsqueda y asignación
        vehicle_id = station.request_vehicle(self, request['destination_station_id'])
        
        if vehicle_id:
            self.stats['successful_requests'] += 1
        else:
            self.stats['failed_requests'] += 1 # Log eliminado para reducir verbosidad
            # print(f"ERROR: Solicitud fallida no hay VMs disponibles para {station.name}")
        
        request['processed'] = True
        request['success'] = vehicle_id is not None
        request['assigned_vehicle'] = vehicle_id
        
        return vehicle_id

    def process_pending_requests(self, dt):
        """
        PROCESA SOLICITUDES PENDIENTES CON CONTROL DE TIEMPO
        ✅ NUEVO: Evita saturación del sistema
        """
        current_time = self.simulation_time
        
        # Verificar si es tiempo de procesar (control de frecuencia)
        if current_time - self.last_request_process_time < self.request_cooldown:
            return
        
        self.last_request_process_time = current_time
        
        if not self.pending_requests:
            return
        
        
        # Procesar solicitudes no procesadas
        unprocessed_requests = [req for req in self.pending_requests if not req['processed']]
        
        for request in unprocessed_requests[:3]:  # Límite de 3 por ciclo
            self._process_single_request(request)
        
        # Limpiar solicitudes procesadas (mantener historial por un tiempo)
        self.pending_requests = [req for req in self.pending_requests 
                               if not req['processed'] or 
                               current_time - req['timestamp'] < 30.0]  # Mantener 30 segundos

    def find_nearest_available_vehicle(self, requesting_station_id):
        """
        ENCUENTRA EL VM DISPONIBLE MÁS CERCANO A UNA ESTACIÓN
        ✅ MEJORADO: Algoritmo de búsqueda más inteligente
        
        Args:
            requesting_station_id: Estación que solicita el VM
            
        Returns:
            ModularVehicle: VM más cercano, o None si no hay disponibles
        """
        available_vehicles = []
        
        for vehicle in self.vehicles.values():
            if self._is_vehicle_available_for_assignment(vehicle, requesting_station_id):
                proximity_score = self._calculate_vehicle_proximity(vehicle, requesting_station_id)
                available_vehicles.append((vehicle, proximity_score))
        
        if not available_vehicles:
            return None
        
        # Ordenar por proximidad (mayor score = más cercano)
        available_vehicles.sort(key=lambda x: x[1], reverse=True)
        
        best_vehicle, best_score = available_vehicles[0]
        
        return best_vehicle

    def _is_vehicle_available_for_assignment(self, vehicle, requesting_station_id):
        """
        VERIFICA SI UN VM ESTÁ DISPONIBLE PARA ASIGNACIÓN
        ✅ NUEVO: Criterios mejorados de disponibilidad
        """
        # No disponible si no está operacional
        if not vehicle.is_operational():
            return False
        
        # ✅ REFINADO: No disponible si ya tiene destino O pasajeros.
        if vehicle.destination_station is not None:
            return False
        
        # ✅ REFINADO: No disponible si lleva pasajeros.
        if vehicle.passengers > 0:
            return False

        # ✅ NUEVO: No disponible si está penalizado para esa estación.
        if vehicle.is_penalized_for_station(requesting_station_id, self.simulation_time):
            return False

        # ✅ NUEVO: No disponible si está en un andén de embarque (BoardingLane).
        if vehicle.current_track and isinstance(vehicle.current_track, BoardingLane):
            return False

        # Disponible si está en movimiento sin destino
        if vehicle.state == "moving" and vehicle.destination_station is None:
            return True

        # Por defecto, no está disponible
        return False

    def _calculate_vehicle_proximity(self, vehicle, target_station_id):
        """
        CALCULA SCORE DE PROXIMIDAD DE UN VM A UNA ESTACIÓN
        ✅ MEJORADO: Prioriza vehículos en tracks que conectan a los árboles de la estación.
        """
        target_station = self.stations.get(target_station_id)
        if not target_station or not vehicle.current_track:
            return 0.0

        # ✅ LÓGICA MEJORADA: Puntuación basada en distancia de red (saltos de track).
        # Usamos una búsqueda en anchura (BFS) para encontrar la ruta más corta en términos de tracks.
        network_dist = self._get_network_distance(vehicle.current_track.track_id, target_station_id)

        if network_dist is None:
            return 0.0 # No hay ruta posible desde este track.

        # La puntuación base es inversamente proporcional a la distancia de red.
        # Un valor alto (ej. 10000) dividido por la distancia.
        # A menor distancia (menos saltos), mayor puntuación.
        score = 10000 / (network_dist + 1)

        # Bonificación adicional por el progreso en el track actual.
        # Un vehículo que está a punto de terminar su track está "más cerca" que uno que acaba de empezar.
        score += vehicle.progress_on_track * 100
        
        return max(0, score)

    def _get_network_distance(self, start_track_id, target_station_id):
        """
        Calcula la "distancia de red" (número de saltos de track) desde un track
        hasta una estación usando Búsqueda en Anchura (BFS).
        """
        target_station = self.stations.get(target_station_id)
        if not target_station:
            return None

        target_arrival_tree_ids = {tree.track_id for tree in target_station.arrival_trees}

        queue = [(start_track_id, 0)]  # (track_id, distancia)
        visited = {start_track_id}

        while queue:
            current_track_id, dist = queue.pop(0)

            # Si el track actual es un árbol de llegada de la estación destino, hemos llegado.
            if current_track_id in target_arrival_tree_ids:
                return dist

            for next_track_id in self.network.adjacency.get(current_track_id, []):
                if next_track_id not in visited:
                    visited.add(next_track_id)
                    queue.append((next_track_id, dist + 1))
        
        return None # No se encontró una ruta

    # ========== ACTUALIZACIÓN PRINCIPAL Y COORDINACIÓN ==========

    def update(self, dt):
        """
        Actualiza el estado del sistema por un paso de tiempo.
        Orden: tren continuo → salidas del tren → red (trees/lanes) → estaciones → colisiones → pasajeros
        """
        self.simulation_time += dt

        # 0. Avanzar el Tren Continuo (mueve TODOS los VMs del carril inferior)
        if self.continuous_train:
            self.continuous_train.advance(dt)

        # 1. Procesar salidas del tren (VMs que toman un árbol de subida)
        self._process_train_exits()

        # 2. Actualizar movimiento en la red (árboles, boarding lanes, NO carril inferior)
        self.network.update_vehicles(dt)

        # 3. Procesar transiciones entre tracks
        self._handle_track_transitions()

        # 4. Procesar operaciones en estaciones
        for station in self.stations.values():
            station.update(self, dt)

        # 5. Gestionar demanda persistente
        self._time_since_last_demand_check += dt
        if self._time_since_last_demand_check >= self._demand_fulfillment_cooldown:
            self._process_station_demand()
            self._time_since_last_demand_check = 0.0

        # 6. Detección de colisiones
        self._check_collisions()

        # 7. Monitoreo del sistema
        if int(self.simulation_time) % 10 == 0:
            self._monitor_system_health()

        # 8. Actualizar pasajeros
        for passenger in self.passengers.values():
            if passenger.state != "ARRIVED":
                passenger.update(dt)

        # 9. Predicciones de colisión usando ContinuousTrain
        self._process_collision_predictions()


    def _process_station_demand(self):
        """Intenta asignar vehículos sin destino a estaciones con demanda."""
        # Itera sobre una copia para permitir la modificación del diccionario durante la iteración
        for station_id, needed in list(self.station_demand.items()):
            if needed <= 0:
                continue

            # Solo intenta satisfacer una unidad de demanda por estación por ciclo de chequeo.
            # La lógica de station.request_vehicle (y su llamada a brain.fulfill_demand)
            # se encargará de decrementar la station_demand si la asignación es exitosa.
            station = self.stations.get(station_id)
            if not station:
                continue

            station.request_vehicle(self)
            # Si vehicle_id es None, significa que no había vehículo disponible para la asignación
            # en este ciclo, y la demanda permanece para el próximo ciclo.

    def _check_collisions(self):
        """
        Verifica colisiones usando una grilla espacial para optimizar.
        """
        # Resetear estado de colisión de todos los vehículos
        for v in self.vehicles.values():
            v.is_colliding = False
            v.colliding_with.clear()

        # 1. Poblar la grilla espacial con la posición actual de todos los vehículos
        self.collision_grid.clear()
        for vehicle in self.vehicles.values():
            self.collision_grid.insert(vehicle)

        # 2. Para cada vehículo, comprobar colisiones solo con sus vecinos cercanos
        for v1 in self.vehicles.values():
            # Obtener solo los vehículos en celdas adyacentes
            nearby_vehicles = self.collision_grid.get_nearby(v1)
            
            for v2 in nearby_vehicles:
                # Evitar dobles comprobaciones y auto-comprobaciones (aunque get_nearby ya lo hace)
                if v1.vehicle_id >= v2.vehicle_id:
                    continue

                bb1_min, bb1_max = v1.get_bounding_box()
                bb2_min, bb2_max = v2.get_bounding_box()
                
                # Comprobación de superposición AABB
                if (bb1_min.x < bb2_max.x and bb1_max.x > bb2_min.x and
                    bb1_min.y < bb2_max.y and bb1_max.y > bb2_min.y and
                    bb1_min.z < bb2_max.z and bb1_max.z > bb2_min.z):
                    v1.is_colliding = True
                    v1.colliding_with.add(v2.vehicle_id)
                    v2.is_colliding = True
                    v2.colliding_with.add(v1.vehicle_id)

    def _handle_track_transitions(self):
        """Maneja las transiciones de vehículos entre tracks (sin cambios)"""
        # Esta lógica está principalmente en Network ahora
        pass

    def _process_collision_predictions(self):
        """
        Gestión preventiva de colisiones en el tren continuo.

        Para cada VM que acaba de entrar a un árbol de bajada:
        1. Calcula el tiempo de llegada a la junction con la aceleración natural (MRUA).
        2. Determina qué slot del tren estará en la junction en ese momento (MRU).
        3. Busca bidireccialmente el slot libre más cercano: centro → +1 → -1 → +2 → -2 ...
        4. Reserva ese slot para que árboles paralelos no lo tomen.
        5. Recalcula la aceleración del VM para que llegue exactamente cuando ese slot
           pase por la junction (llegada fluida, sin esperas ni frenasos).
        6. Si no hay slots libres en el rango configurado → colisión inevitable,
           ajusta igualmente la aceleración para llegar fluido al slot ocupado.
        """
        if not self.continuous_train:
            self.pending_down_tree_entries.clear()
            return

        train = self.continuous_train

        for event in self.pending_down_tree_entries:
            vehicle = event['vehicle']
            from_track = event['from_track']
            descending_tree = event['descending_tree']

            # ── 1. Tiempo natural de bajada (MRUA con aceleración propia del árbol) ──
            start_progress = descending_tree.get_vehicle_progress(vehicle)
            v0 = from_track.speed if hasattr(from_track, 'speed') else 20.0
            T_natural = descending_tree.get_time_to_complete(
                initial_velocity=v0, start_progress=start_progress
            )
            if T_natural is None or T_natural <= 0:
                continue

            # ── 2. Encontrar la junction belt_x (donde el árbol desemboca al carril) ──
            junction_belt_x = None
            for tid in self.network.adjacency.get(descending_tree.track_id, []):
                if tid in self.network.lower_rail_track_ids:
                    junction_belt_x = train.junction_belt_x[tid]
                    break
            if junction_belt_x is None:
                continue

            # ── 3. Calcular el slot "natural" (qué slot estará en junction en T_natural) ──
            # Posición futura de la cola del tren: MRU → x = x₀ + v*t
            future_tail_x = (train.tail_x + train.speed * T_natural) % train.total_length
            delta = (junction_belt_x - future_tail_x) % train.total_length
            natural_slot = round(delta / train.spacing)
            if natural_slot >= train.max_slots:
                natural_slot = 0

            # ── 4. Liberar reserva previa del VM y buscar slot objetivo ──
            # (puede haber una reserva de un descenso anterior si el VM volvió a bajar)
            train.release_reservation(vehicle.vehicle_id)
            target_slot, is_forced_collision = train.find_target_slot_bidirectional(
                natural_slot, self.slot_search_range
            )

            # ── 5. Calcular T_target: tiempo al que target_slot pasa por la junction ──
            # Cada slot de diferencia equivale a spacing/speed segundos de desfase.
            # Un slot con índice mayor está más adelante → pasa la junction ANTES (T menor).
            # Un slot con índice menor está más atrás  → pasa la junction DESPUÉS (T mayor).
            delta_slot = target_slot - natural_slot
            # Corrección por wrap-around (si el salto es más de la mitad del tren)
            if delta_slot > train.max_slots // 2:
                delta_slot -= train.max_slots
            elif delta_slot < -(train.max_slots // 2):
                delta_slot += train.max_slots

            T_target = T_natural - delta_slot * train.spacing / train.speed

            # Garantizar que T_target sea positivo (wrap-around extremo, muy improbable)
            cycle_time = train.total_length / train.speed
            if T_target <= 0:
                T_target += cycle_time

            # ── 6. Calcular aceleración requerida: L = v0·T + ½·a·T² → a = 2(L-v0·T)/T² ──
            L = descending_tree.length * (1.0 - start_progress)  # longitud restante
            if T_target > 0:
                a_required = 2.0 * (L - v0 * T_target) / (T_target ** 2)
            else:
                a_required = self.accel_range_max

            # Acotar dentro del rango configurable para evitar aceleraciones disparatadas
            a_clamped = max(self.accel_range_min, min(self.accel_range_max, a_required))

            # ── 7. Reservar slot y aplicar aceleración modificada al VM ──
            train.reserve_slot(target_slot, vehicle.vehicle_id)
            descending_tree.set_vehicle_acceleration(vehicle, a_clamped)

            # ── 8. Notificaciones en terminal ──
            if is_forced_collision:
                conflicting_vm = train.get_vm_at_slot(target_slot)
                conflicting_id = conflicting_vm.vehicle_id if conflicting_vm else "desconocido"
                print(f"\n{'='*45}")
                print(f"[TREN] COLISION INEVITABLE — VM {vehicle.vehicle_id}")
                print(f"  Arbol de bajada : {descending_tree.track_id}")
                print(f"  Sin slots libres en rango ±{self.slot_search_range}")
                print(f"  Colisionara con : VM {conflicting_id} en slot {target_slot}")
                print(f"  T llegada       : {T_target:.2f}s  (natural: {T_natural:.2f}s)")
                print(f"  Aceleracion     : {a_clamped:.4f} m/s²  "
                      f"(requerida: {a_required:.4f}, natural: {descending_tree.acceleration:.4f})")
                print(f"{'='*45}\n")
            else:
                # Calcular el offset real para el mensaje (con signo correcto post wrap-around)
                if delta_slot == 0:
                    print(f"[TREN] VM {vehicle.vehicle_id} → slot {target_slot} RESERVADO  "
                          f"(arbol {descending_tree.track_id} | T={T_target:.2f}s | "
                          f"a={a_clamped:.4f} m/s²)")
                else:
                    sign = "+" if delta_slot > 0 else ""
                    print(f"\n{'='*45}")
                    print(f"[TREN] COLISION PREVENIDA — VM {vehicle.vehicle_id}")
                    print(f"  Arbol de bajada : {descending_tree.track_id}")
                    print(f"  Slot natural {natural_slot} ocupado/reservado "
                          f"→ slot alternativo {target_slot} (offset {sign}{delta_slot})")
                    print(f"  T ajustado      : {T_target:.2f}s  "
                          f"(natural: {T_natural:.2f}s, delta: {T_target - T_natural:+.2f}s)")
                    print(f"  Aceleracion     : {a_clamped:.4f} m/s²  "
                          f"(requerida: {a_required:.4f}, natural: {descending_tree.acceleration:.4f})")
                    print(f"{'='*45}\n")

        self.pending_down_tree_entries.clear()

    def _process_train_exits(self):
        """
        Cada frame, verifica si algún VM del tren está en una junction de salida
        y debería tomar un árbol de subida (basado en su destino).
        """
        if not self.continuous_train or not self._train_exit_junctions:
            return

        for junction in self._train_exit_junctions:
            belt_x = junction['belt_x']
            up_tree_ids = junction['up_tree_ids']

            # Encontrar el slot más cercano a esta junction
            slot_index = self.continuous_train.belt_x_to_slot_index(belt_x)
            vm = self.continuous_train.get_vm_at_slot(slot_index)

            if vm is None:
                continue

            # ¿El VM tiene un destino que requiere uno de estos árboles?
            if not vm.target_acceleration_trees:
                continue

            matching_tree_ids = [tid for tid in up_tree_ids if tid in vm.target_acceleration_trees]
            if not matching_tree_ids:
                continue

            # Usar TreeSelector para elegir el mejor árbol
            valid_trees = [self.network.tracks[tid] for tid in matching_tree_ids if tid in self.network.tracks]
            best_tree = self.network.tree_selector.select_best_tree(
                valid_trees, vm,
                strategy='progressive_saturation',
                station_id=vm.destination_station
            )

            if best_tree and best_tree.can_accept_vehicle(vm):
                # Sacar del tren
                self.continuous_train.remove_vm(vm)
                # Transferir al árbol de subida (velocidad de entrada = velocidad del tren)
                vm.transfer_to_track(best_tree, entry_velocity=self.continuous_train.speed)

    def _monitor_system_health(self):
        """
        MONITOREO MEJORADO - Incluye estado de árboles
        """
        # Estado de vehículos por tipo de track
        on_acceleration_trees = sum(1 for v in self.vehicles.values() 
                                if v.current_track and isinstance(v.current_track, AccelerationTree))
        
        # Estado de capacidad de estaciones
        for station in self.stations.values():
            capacity_info = station.get_arrival_capacity_info()
            status = "Susses" if capacity_info['available'] else "ERROR"
            
    
    # ========== MÉTODOS DE CONSULTA Y ESTADÍSTICAS ==========

    def get_system_status(self):
        """
        Retorna el estado actual del sistema para debug
        MEJORADO: Incluye información del TreeSelector y estadísticas
        """
        # Estado base (existente)
        status = {
            "simulation_time": self.simulation_time,
            "total_vehicles": len(self.vehicles),
            "vehicles_by_state": {},
            "stations": len(self.stations),
            "pending_requests": len(self.pending_requests),
            "stats": self.stats.copy()
        }
        
        # Contar vehículos por estado (existente)
        for vehicle in self.vehicles.values():
            state = vehicle.state
            status["vehicles_by_state"][state] = status["vehicles_by_state"].get(state, 0) + 1
        
        # ✅ NUEVO: Información de capacidad del sistema
        status["system_capacity"] = self._get_system_capacity_report()
        
        # ✅ NUEVO: Información de navegación si está disponible
        if hasattr(self.network, 'get_navigation_status'):
            status["navigation"] = self.network.get_navigation_status()
        
        return status

    def _get_system_capacity_report(self):
        """
        GENERA REPORTE DE CAPACIDAD DEL SISTEMA
        ✅ NUEVO: Para monitoreo y toma de decisiones
        """
        report = {
            "total_stations": len(self.stations),
            "stations_with_capacity": 0,
            "stations_at_capacity": 0,
            "total_arrival_trees": 0,
            "available_arrival_trees": 0,
            "station_details": {}
        }
        
        for station in self.stations.values():
            capacity_info = station.get_arrival_capacity_info()
            report["total_arrival_trees"] += capacity_info["total_trees"]
            report["available_arrival_trees"] += len(capacity_info["available_trees"])
            
            if capacity_info["available"]:
                report["stations_with_capacity"] += 1
            else:
                report["stations_at_capacity"] += 1
            
            report["station_details"][station.station_id] = {
                "name": station.name,
                "has_capacity": capacity_info["available"],
                "available_trees": len(capacity_info["available_trees"]),
                "total_trees": capacity_info["total_trees"]
            }
        
        return report

    def get_vehicles_en_route_to(self, station_id):
        """
        Retorna una lista de vehículos que se dirigen a una estación específica.
        
        Args:
            station_id: El ID de la estación de destino.
            
        Returns:
            list: Una lista de objetos ModularVehicle en ruta a la estación.
        """
        return [v for v in self.vehicles.values() if v.destination_station == station_id]


    def get_vehicle_distribution(self):
        """
        DISTRIBUCIÓN DE VEHÍCULOS POR ESTADO Y UBICACIÓN
        ✅ NUEVO: Para análisis y balanceo del sistema
        """
        distribution = {
            "by_state": {},
            "by_station": {},
            "by_track_type": {
                "station_connector": 0,
                "acceleration_tree_up": 0,
                "acceleration_tree_down": 0
            }
        }
        
        for vehicle in self.vehicles.values():
            # Por estado
            state = vehicle.state
            distribution["by_state"][state] = distribution["by_state"].get(state, 0) + 1
            
            # Por estación
            if vehicle.current_station:
                station_id = vehicle.current_station
                distribution["by_station"][station_id] = distribution["by_station"].get(station_id, 0) + 1
            
            # Por tipo de track
            if vehicle.current_track:
                if hasattr(vehicle.current_track, 'get_track_type'):
                    track_type = vehicle.current_track.get_track_type()
                    if track_type == "StationConnector":
                        distribution["by_track_type"]["station_connector"] += 1
                    elif track_type == "AccelerationTree":
                        if vehicle.current_track.direction == "up":
                            distribution["by_track_type"]["acceleration_tree_up"] += 1
                        else:
                            distribution["by_track_type"]["acceleration_tree_down"] += 1
        
        return distribution

    def emergency_reroute_vehicles(self, congested_station_id):
        """
        REASIGNACIÓN DE EMERGENCIA PARA ESTACIONES CONGESTIONADAS
        Mecanismo de recuperación automática
        """
        print(f"🚨 INICIANDO REASIGNACIÓN DE EMERGENCIA PARA ESTACIÓN {congested_station_id}")
        
        rerouted_count = 0
        for vehicle in self.vehicles.values():
            if (vehicle.destination_station == congested_station_id and 
                vehicle.state not in ["accelerating_up"]): # Ya no existe 'docked'
                
                # Encontrar estación alternativa
                alternative_station = self._find_alternative_station(congested_station_id)
                if alternative_station:
                    vehicle.destination_station = alternative_station.station_id
                    vehicle.target_acceleration_trees = self._find_optimal_target_trees(
                        alternative_station.station_id, vehicle
                    )
                    rerouted_count += 1
                    print(f"   🔀 VM {vehicle.vehicle_id} redirigido a {alternative_station.name}")
        
        return rerouted_count

    def _find_alternative_station(self, congested_station_id):
        """
        ENCUENTRA ESTACIÓN ALTERNATIVA PARA REASIGNACIÓN
        ✅ NUEVO: Lógica de selección de alternativas
        """
        # Buscar estación con mejor capacidad
        best_station = None
        best_capacity_score = -1
        
        for station in self.stations.values():
            if station.station_id == congested_station_id:
                continue
                
            capacity_info = station.get_arrival_capacity_info()
            if capacity_info["available"]:
                # Score basado en capacidad disponible
                capacity_score = len(capacity_info["available_trees"]) * 10
                
                if capacity_score > best_capacity_score:
                    best_capacity_score = capacity_score
                    best_station = station
        
        return best_station

    # ========== MÉTODOS DE DIAGNÓSTICO Y DEBUG ==========

    def validate_system_state(self):
        """
        VALIDACIÓN DEL ESTADO DEL SISTEMA
        ✅ NUEVO: Verificación de consistencia para debugging
        """
        issues = []
        
        # Verificar que todos los vehículos tienen estado válido
        for vehicle in self.vehicles.values():
            if not vehicle.current_track and vehicle.state not in ["maintenance"] and not vehicle.current_station:
                issues.append(f"Vehículo {vehicle.vehicle_id} sin track pero estado {vehicle.state}")
        
        # Verificar que las estaciones tienen árboles
        for station in self.stations.values():
            if not station.arrival_trees:
                issues.append(f"Estación {station.name} sin árboles de llegada")
            if not station.departure_trees:
                issues.append(f"Estación {station.name} sin árboles de salida")
        
        if issues:
            print("⚠️  PROBLEMAS DETECTADOS EN LA VALIDACIÓN:")
            for issue in issues:
                print(f"   - {issue}")
            return False
        else:
            return True

    def get_detailed_vehicle_report(self, vehicle_id):
        """
        REPORTE DETALLADO DE UN VEHÍCULO ESPECÍFICO
        ✅ NUEVO: Para debugging y monitoreo específico
        """
        vehicle = self.vehicles.get(vehicle_id)
        if not vehicle:
            return {"error": f"Vehículo {vehicle_id} no encontrado"}
        
        report = vehicle.get_vehicle_info()
        
        # Información adicional del sistema
        if vehicle.current_station:
            station = self.stations.get(vehicle.current_station)
            if station:
                report["current_station_info"] = {
                    "name": station.name,
                    "capacity": station.get_arrival_capacity_info()
                }
        
        if vehicle.destination_station:
            destination = self.stations.get(vehicle.destination_station)
            if destination:
                report["destination_station_info"] = {
                    "name": destination.name,
                    "capacity": destination.get_arrival_capacity_info()
                }
        
        return report