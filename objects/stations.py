from objects.base import Vector3

class Station:
    """
    ESTACIÓN FÍSICA DEL SISTEMA DE TRANSPORTE
    
    Responsabilidades PRINCIPALES (Primera Etapa):
    - Gestionar vehículos docked (estacionados)
    - Administrar árboles de aceleración de llegada y salida
    - Coordinar con TreeSelector para asignación óptima de árboles
    - Preparar infraestructura para sistema de pasajeros
    
    Responsabilidades NO incluidas (para futuras etapas):
    - Gestión de pasajeros reales (solo simulado por ahora)
    - Gestión de andenes/lanes (se agregará después)
    - Toma de decisiones de routing complejas (lo hace Brain/Network)
    """

    def __init__(self, station_id, name, position, target_vehicles_per_minute=0.0):
        self.station_id = station_id
        self.name = name
        self.position = position  # Vector3 - posición en superficie
        self.arrival_trees = []   # Lista de AccelerationTree (dirección 'up')
        self.departure_trees = [] # Lista de AccelerationTree (dirección 'down')

        # TreeSelector para gestión inteligente de árboles
        self.tree_selector = None
        
        # Preparación para sistema de andenes (futura implementación)
        self.lanes = []  # Se poblará cuando implementemos el sistema de lanes
        self.passenger_count = 0  # Simulado por ahora

        # ✅ NUEVO: Gestión de demanda de vehículos
        self.target_vehicles_per_minute = target_vehicles_per_minute
        self._request_check_interval = 10.0  # Segundos, frecuencia de chequeo
        self._time_since_last_check = 0.0
        self._demand_accumulator = 0.0 # ✅ NUEVO: Acumulador para demanda fraccional
        

    # ========== CONFIGURACIÓN Y INYECCIÓN DE DEPENDENCIAS ==========

    def set_tree_selector(self, tree_selector):
        """
        Configura el TreeSelector para esta estación
        
        Args:
            tree_selector: Instancia de TreeSelector compartida
        """
        self.tree_selector = tree_selector

    def add_arrival_tree(self, acceleration_tree):
        """
        Agrega un árbol de aceleración de LLEGADA a la estación
        """
        if acceleration_tree.direction != 'up':
            raise ValueError("Los árboles de llegada deben tener dirección 'up'")
        
        self.arrival_trees.append(acceleration_tree)
        
        # Actualizar información de capacidad
        self._update_capacity_info()
    
    def add_departure_tree(self, acceleration_tree):
        """
        Agrega un árbol de aceleración de SALIDA de la estación
        """
        if acceleration_tree.direction != 'down':
            raise ValueError("Los árboles de salida deben tener dirección 'down'")
        
        self.departure_trees.append(acceleration_tree)

    # ========== SOLICITUD Y ASIGNACIÓN DE VEHÍCULOS ==========

    def request_vehicle(self, brain, destination_station_id=None):
        """
        SOLICITA UN VM PARA VENIR A ESTA ESTACIÓN
        Implementación completa con verificaciones de capacidad
        
        Args:
            brain: Instancia de Brain para encontrar VMs
            destination_station_id: Destino final del pasajero (opcional)
            
        Returns:
            str: ID del VM asignado, o None si no hay disponibles
        """
        # print(f"Estación {self.name} solicitando VM...") # Log reducido para no saturar consola
        
        # 1. BUSCAR VM DISPONIBLE (Se eliminó la comprobación de capacidad previa)
        vehicle = brain.find_nearest_available_vehicle(self.station_id)
        if not vehicle:
            # print(f"INFO: No hay VMs disponibles para estación {self.name} en este ciclo.") # Log desactivado para reducir ruido
            return None
        
        # 3. ASIGNAR DESTINO Y RUTA ÓPTIMA
        # ✅ SOLUCIÓN PROBLEMA 1: Asignar TODOS los árboles de llegada posibles.
        # El vehículo y la red decidirán cuál usar en tiempo real.
        all_arrival_trees = [tree.track_id for tree in self.arrival_trees]
        if not all_arrival_trees:
            print(f"ERROR: {self.name} no tiene árboles de llegada configurados.")
            return None

        vehicle.assign_destination(self.station_id, all_arrival_trees)
        
        print(f"✅ VM {vehicle.vehicle_id} asignado a {self.name}. Opciones de llegada: {all_arrival_trees}")
        
        return vehicle.vehicle_id

    def select_optimal_arrival_tree(self, vehicle):
        """
        SELECCIONA EL ÁRBOL DE LLEGADA ÓPTIMO PARA UN VM
        ✅ NUEVO: Delega en TreeSelector con estrategia apropiada
        
        Args:
            vehicle: Vehículo que va a llegar
            
        Returns:
            AccelerationTree: Árbol seleccionado, o None si no hay disponibles
        """
        if not self.tree_selector or not self.arrival_trees:
            return None
            
        # Seleccionar estrategia basada en condiciones actuales
        strategy = self.tree_selector.get_strategy_recommendation(
            self.arrival_trees, 
            self.station_id
        )
        
        
        # Delegar selección al TreeSelector
        return self.tree_selector.select_best_tree(
            self.arrival_trees, 
            vehicle, 
            strategy=strategy,
            station_id=self.station_id
        )

    # ========== GESTIÓN DE CAPACIDAD Y ESTADO ==========

    def has_arrival_capacity(self):
        """
        VERIFICA SI LA ESTACIÓN PUEDE ACEPTAR NUEVOS VEHÍCULOS
        ✅ NUEVO: Verifica tanto capacidad docked como árboles de llegada
        """
        # Verificar que hay al menos un árbol de llegada disponible
        if not self.arrival_trees:
            return False
            
        # Verificar que al menos un árbol puede aceptar vehículos
        if self.tree_selector:
            return self.tree_selector.validate_tree_selection(self.arrival_trees, None)
        else:
            # Fallback: verificar manualmente
            return any(tree.can_accept_vehicle(None) for tree in self.arrival_trees)

    def get_arrival_capacity_info(self):
        """
        INFORMACIÓN DETALLADA DE CAPACIDAD DE LLEGADA
        ✅ NUEVO: Para monitoreo y toma de decisiones
        """
        if not self.arrival_trees:
            return {"available": False, "reason": "No hay árboles de llegada"}
        
        available_trees = []
        for tree in self.arrival_trees:
            if tree.can_accept_vehicle(None):
                available_trees.append({
                    'track_id': tree.track_id,
                    'occupancy': tree.get_occupancy_info()
                })
        
        return {
            'available': len(available_trees) > 0,
            'available_trees': available_trees,
            'total_trees': len(self.arrival_trees)
        }

    def _update_capacity_info(self):
        """
        ACTUALIZA INFORMACIÓN INTERNA DE CAPACIDAD
        ✅ NUEVO: Para mantener consistencia del estado
        """
        # Por ahora solo logs, pero se puede extender para ajustes automáticos
        capacity_info = self.get_arrival_capacity_info()
        if capacity_info['available']:
            print(f"📊 {self.name}: {len(capacity_info['available_trees'])}/{capacity_info['total_trees']} árboles disponibles")
        else:
            print(f"⚠️  {self.name}: Sin capacidad de llegada disponible")

    def _get_destination_arrival_trees(self, destination_station_id):
        """
        OBTIENE ÁRBOLES DE LLEGADA DE UNA ESTACIÓN DESTINO
        ✅ NUEVO: Para planificación de rutas (delegaría en Brain en implementación real)
        """
        # Esta es una implementación simplificada
        # En una implementación real, esto lo proporcionaría Brain o Network
        print(f"   🔍 Buscando árboles de llegada para estación {destination_station_id}")
        # Por ahora retornamos lista vacía - se implementará cuando tengamos
        # acceso al grafo completo de estaciones
        return []

    # ========== PROCESAMIENTO DE OPERACIONES ==========

    def receive_vehicle(self, vehicle, arrival_tree):
        """
        RECIBE UN VEHÍCULO QUE LLEGA A TRAVÉS DE UN ÁRBOL DE LLEGADA
        Ahora transfiere el vehículo directamente al siguiente track.
        """
        if arrival_tree not in self.arrival_trees:
            print(f"ERROR: Árbol {arrival_tree.track_id} no pertenece a estación {self.name}")
            return False
        
        # La lógica de transferencia ahora está centralizada en Network._transfer_vehicle
        # Esta función es llamada por Network cuando un vehículo llega a un árbol de subida.
        # Aquí solo actualizamos el estado del vehículo.
        vehicle.arrive_at_station(self.station_id)
        print(f"Vehículo {vehicle.vehicle_id} ha pasado por la estación {self.name}")
        return True

    # ========== MÉTODOS DE CONSULTA E INFORMACIÓN ==========

    def get_station_info(self):
        """
        RETORNA INFORMACIÓN COMPLETA DE LA ESTACIÓN
        MEJORADO: Incluye información de capacidad y TreeSelector
        """
        capacity_info = self.get_arrival_capacity_info()
        
        info = {
            "station_id": self.station_id,
            "name": self.name,
            "position": self.position.to_tuple(),
            "arrival_trees": [tree.track_id for tree in self.arrival_trees],
            "departure_trees": [tree.track_id for tree in self.departure_trees],
            "status": "OPERATIONAL",
            "tree_selector_configured": self.tree_selector is not None,
            "arrival_capacity": capacity_info
        }
        
        # Agregar información de árboles si hay TreeSelector
        if self.tree_selector and self.arrival_trees:
            trees_status = self.tree_selector.get_trees_status(self.arrival_trees)
            info["trees_status"] = trees_status
            
        return info

    def update(self, brain, dt):
        """
        Actualiza el estado de la estación (para ser llamado cada frame)
        ✅ NUEVO: Gestiona la demanda de vehículos según la tasa configurada.
        """
        self._time_since_last_check += dt

        if self._time_since_last_check >= self._request_check_interval:
            self._manage_vehicle_demand(brain)
            self._time_since_last_check = 0.0

    def _manage_vehicle_demand(self, brain):
        """Verifica y satisface la demanda de vehículos de la estación."""
        if self.target_vehicles_per_minute <= 0:
            return

        # 1. Calcular la "deuda" de vehículos acumulada en este intervalo.
        # Esto permite que tasas muy bajas (e.g., 1 VM/min) se acumulen con el tiempo.
        vehicles_needed_this_interval = (self.target_vehicles_per_minute / 60.0) * self._request_check_interval
        self._demand_accumulator += vehicles_needed_this_interval

        # 2. Consultar al cerebro cuántos vehículos ya vienen en camino y cuánta demanda hay pendiente.
        vehicles_en_route = brain.get_vehicles_en_route_to(self.station_id)
        pending_demand = brain.station_demand.get(self.station_id, 0)

        # 3. El "déficit real" es lo que hemos acumulado menos lo que ya está gestionado (en ruta o en cola).
        effective_demand = self._demand_accumulator - (len(vehicles_en_route) + pending_demand)

        # 4. Si el acumulador supera 1, es hora de solicitar al menos un vehículo.
        if effective_demand >= 1.0:
            vehicles_to_request = int(effective_demand)
            print(f"📈 {self.name}: Demanda acumulada ({self._demand_accumulator:.2f}). Solicitando {vehicles_to_request} VM(s).")
            
            # Registrar la nueva demanda en el Brain
            brain.register_demand(self.station_id, vehicles_to_request)
            
            # Restar del acumulador lo que acabamos de solicitar.
            self._demand_accumulator -= vehicles_to_request