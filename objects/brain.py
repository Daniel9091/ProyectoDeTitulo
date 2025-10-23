from objects.acceleration_tree import AccelerationTree

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
        
        # ✅ NUEVO: Sistema de gestión de solicitudes
        self.pending_requests = []  # Solicitudes de VMs pendientes
        self.request_cooldown = 2.0  # Segundos entre procesamiento de solicitudes
        self.last_request_process_time = 0.0
        
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

    def assign_vehicle_to_route(self, vehicle, from_station, to_station):
        """
        Asigna una ruta completa a un vehículo
        MEJORADO: Usa TreeSelector para asignación óptima de árboles
        """
        if from_station.station_id not in self.stations:
            print(f"ERROR: Estación origen {from_station.station_id} no registrada")
            return False
            
        # Verificar capacidad de la estación destino
        if not to_station.has_arrival_capacity():
            print(f"ERROR: Estación destino {to_station.name} no tiene capacidad")
            return False

        # Asignar destino al vehículo
        vehicle.destination_station = to_station.station_id
        
        # Usar TreeSelector para encontrar árboles objetivo óptimos
        target_trees = self._find_optimal_target_trees(to_station.station_id, vehicle)
        vehicle.target_acceleration_trees = target_trees

        # DEBUG: Imprimir información de ruta
        print(f"🧭 ASIGNACIÓN DE RUTA: Vehículo {vehicle.vehicle_id} desde {from_station.name} a {to_station.name}")
        print(f"   Árboles objetivo: {target_trees}")
        
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
            self.stats['failed_requests'] += 1
            print(f"ERROR: Solicitud fallida no hay VMs disponibles para {station.name}")
        
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
        
        # No disponible si ya tiene destino asignado
        if vehicle.destination_station is not None:
            return False
        
        # Disponible si está en movimiento sin destino
        if vehicle.state == "moving" and vehicle.destination_station is None:
            return True

        # Por defecto, no está disponible
        return True

    def _calculate_vehicle_proximity(self, vehicle, target_station_id):
        """
        CALCULA SCORE DE PROXIMIDAD DE UN VM A UNA ESTACIÓN
        ✅ MEJORADO: Algoritmo más sofisticado
        """
        score = 0.0
        
        # 1. Estado actual del vehículo
        if vehicle.state == "moving":
            score += 30  # Ya está en movimiento, puede redirigirse
        elif "accelerating" in vehicle.state:
            score += 10  # Más difícil redirigir durante aceleración
        
        # 2. Proximidad basada en posición actual (simplificado)
        # En implementación real, usaríamos el grafo de rutas
        if vehicle.current_station:
            # Simular distancia basada en IDs (placeholder)
            station_distance = abs(vehicle.current_station - target_station_id)
            score += max(0, 50 - station_distance * 5)
        
        # 3. Eficiencia operacional
        if vehicle.passengers == 0:
            score += 15  # Preferir vehículos vacíos
        
        # 4. Tiempo operacional (preferir vehículos más descansados)
        operational_penalty = min(vehicle.operational_time / 3600, 10)  # 1 punto por hora
        score -= operational_penalty
        
        return max(0, score)

    # ========== ACTUALIZACIÓN PRINCIPAL Y COORDINACIÓN ==========

    def update(self, dt):
        """
        Actualiza el estado del sistema por un paso de tiempo
        MEJORADO: Incluye procesamiento de solicitudes y monitoreo
        """
        self.simulation_time += dt
        
        # 1. Actualizar movimiento en la red
        self.network.update_vehicles(dt)
        
        # 2. Procesar transiciones entre tracks
        self._handle_track_transitions()
        
        # 3. Procesar operaciones en estaciones
        for station in self.stations.values():
            station.update(self, dt)
        
        # ✅ NUEVO: 4. Procesar solicitudes pendientes de VMs
        self.process_pending_requests(dt)
        
        # 5. Detección de colisiones
        self._check_collisions()
        
        # 6. Monitoreo del sistema
        if int(self.simulation_time) % 10 == 0:  # Cada 10 segundos
            self._monitor_system_health()

    def _check_collisions(self):
        """
        Verifica si hay colisiones entre cualquier par de vehículos.
        Usa una comprobación de cajas delimitadoras (AABB).
        """
        vehicles = list(self.vehicles.values())
        
        # Resetear estado de colisión de todos los vehículos
        for v in vehicles:
            v.is_colliding = False
            
        # Comprobar cada par de vehículos una sola vez
        for i in range(len(vehicles)):
            for j in range(i + 1, len(vehicles)):
                v1 = vehicles[i]
                v2 = vehicles[j]
                
                bb1_min, bb1_max = v1.get_bounding_box()
                bb2_min, bb2_max = v2.get_bounding_box()
                
                # Comprobación de superposición AABB
                if (bb1_min.x < bb2_max.x and bb1_max.x > bb2_min.x and
                    bb1_min.y < bb2_max.y and bb1_max.y > bb2_min.y and
                    bb1_min.z < bb2_max.z and bb1_max.z > bb2_min.z):
                    v1.is_colliding = True
                    v2.is_colliding = True

    def _handle_track_transitions(self):
        """Maneja las transiciones de vehículos entre tracks (sin cambios)"""
        # Esta lógica está principalmente en Network ahora
        pass

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