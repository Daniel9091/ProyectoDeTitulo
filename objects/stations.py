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

    def __init__(self, station_id, name, position):
        self.station_id = station_id
        self.name = name
        self.position = position  # Vector3 - posición en superficie
        self.arrival_trees = []   # Lista de AccelerationTree (dirección 'up')
        self.departure_trees = [] # Lista de AccelerationTree (dirección 'down')
        self.docked_vehicles = [] # Lista de ModularVehicle estacionados
        self.capacity = 10  # Capacidad máxima de vehículos docked
        
        # TreeSelector para gestión inteligente de árboles
        self.tree_selector = None
        
        # Preparación para sistema de andenes (futura implementación)
        self.lanes = []  # Se poblará cuando implementemos el sistema de lanes
        self.passenger_count = 0  # Simulado por ahora
        

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

    # ========== GESTIÓN DE VEHÍCULOS DOCKED ==========

    def dock_vehicle(self, vehicle):
        """
        Estaciona un vehículo en la estación (llegada)
        MEJORADO: Validaciones mejoradas y logs informativos
        """
        if len(self.docked_vehicles) >= self.capacity:
            print(f"ERROR: Estación {self.name} está a capacidad máxima")
            return False
        
        if vehicle in self.docked_vehicles:
            print(f"ADVERTENCIA: Vehículo {vehicle.vehicle_id} ya está en estación {self.name}")
            return False
        
        self.docked_vehicles.append(vehicle)
        vehicle.current_station = self.station_id
        vehicle.state = "docked"
        vehicle.current_track = None
        
        # MEJORADO: Limpiar información de ruta al llegar
        if vehicle.destination_station == self.station_id:
            vehicle.destination_station = None  # Destino cumplido
            vehicle.target_acceleration_trees = []  # Limpiar ruta
            print(f"🎯 Vehículo {vehicle.vehicle_id} llegó a su DESTINO FINAL: {self.name}")
        else:
            print(f"🔄 Vehículo {vehicle.vehicle_id} llegó a estación {self.name} (en tránsito)")
            
        return True

    def undock_vehicle(self, vehicle, destination_station_id):
        """
        Prepara un vehículo para salir de la estación con un destino
        MEJORADO: Integración con TreeSelector para rutas óptimas
        """
        if vehicle not in self.docked_vehicles:
            print(f"ERROR: Vehículo {vehicle.vehicle_id} no está en estación {self.name}")
            return False
        
        if not self.departure_trees:
            print(f"ERROR: Estación {self.name} no tiene árboles de salida")
            return False
        
        # Asignar destino al vehículo
        vehicle.destination_station = destination_station_id
        
        # ✅ NUEVO: Usar TreeSelector para encontrar árboles objetivo óptimos
        if self.tree_selector:
            target_station_trees = self._get_destination_arrival_trees(destination_station_id)
            if target_station_trees:
                # Seleccionar el mejor árbol usando TreeSelector
                optimal_tree = self.tree_selector.select_best_tree(
                    target_station_trees, 
                    vehicle,
                    strategy='progressive_saturation',
                    station_id=destination_station_id
                )
                
                if optimal_tree:
                    vehicle.target_acceleration_trees = [optimal_tree.track_id]
                    print(f"🎯 Ruta asignada: {self.name} -> Estación {destination_station_id} (Árbol {optimal_tree.track_id})")
                else:
                    # Fallback: usar todos los árboles disponibles
                    vehicle.target_acceleration_trees = [tree.track_id for tree in target_station_trees]
                    print(f"⚠️  No se pudo seleccionar árbol óptimo, usando todos los disponibles")
            else:
                vehicle.target_acceleration_trees = []
                print(f"⚠️  No se encontraron árboles de llegada en la estación destino")
        
        vehicle.state = "ready_to_depart"
        
        print(f"🚀 Vehículo {vehicle.vehicle_id} preparado para salir de {self.name} hacia estacion {destination_station_id}")
        return True

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
        print(f"Estación {self.name} solicitando VM...")
        
        # 1. VERIFICAR CAPACIDAD DE LLEGADA
        if not self.has_arrival_capacity():
            print(f"ERROR: Estación {self.name} no tiene capacidad de llegada")
            return None
        
        # 2. BUSCAR VM DISPONIBLE
        vehicle = brain.find_nearest_available_vehicle(self.station_id)
        if not vehicle:
            print(f"ERROR: No hay VMs disponibles para estación {self.name}")
            return None
        
        # 3. ASIGNAR DESTINO Y RUTA ÓPTIMA
        vehicle.destination_station = self.station_id
        
        # Selección inteligente del árbol de llegada
        optimal_arrival_tree = self.select_optimal_arrival_tree(vehicle)
        if not optimal_arrival_tree:
            print(f"ERROR: No hay árboles de llegada disponibles en {self.name}")
            vehicle.destination_station = None  # Revertir asignación
            return None
        
        vehicle.target_acceleration_trees = [optimal_arrival_tree.track_id]
        

        print(f"   Árbol de llegada asignado: {optimal_arrival_tree.track_id}")
        print(f"   Destino final: {'Estación ' + str(destination_station_id) if destination_station_id else 'Ninguno (solo recogida)'}")
        
        # 4. INICIAR VIAJE SI ESTÁ EN OTRA ESTACIÓN
        if vehicle.state == "docked" and vehicle.current_station:
            current_station = brain.stations.get(vehicle.current_station)
            if current_station:
                success = current_station.undock_vehicle(vehicle, self.station_id)
                if not success:
                    print(f"ERROR: No se pudo iniciar viaje desde estación {current_station.name}")
                    return None
        
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
        # Verificar capacidad de docking
        if len(self.docked_vehicles) >= self.capacity:
            return False
            
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
            'total_trees': len(self.arrival_trees),
            'docked_vehicles': len(self.docked_vehicles),
            'docking_capacity': self.capacity,
            'docking_available': len(self.docked_vehicles) < self.capacity
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

    def process_departures(self, brain):
        """
        PROCESA VEHÍCULOS LISTOS PARA SALIR
        MEJORADO: Más eficiente y con mejor logging
        """
        vehicles_to_depart = [
            vehicle for vehicle in self.docked_vehicles 
            if vehicle.state == "ready_to_depart" and vehicle.destination_station
        ]
        
        if not vehicles_to_depart:
            return
            
        print(f"🚀 Estación {self.name}: Procesando {len(vehicles_to_depart)} salidas")
        
        for vehicle in vehicles_to_depart:
            success = self._depart_vehicle(vehicle, brain)
            if not success:
                print(f"ERROR: al procesar salida de VM {vehicle.vehicle_id}")

    def _depart_vehicle(self, vehicle, brain):
        """
        ENVÍA UN VEHÍCULO DESDE LA ESTACIÓN
        MEJORADO: Manejo de errores robusto
        """
        if not self.departure_trees:
            return False
            
        # Seleccionar árbol de salida (estrategia simple por ahora)
        departure_tree = self.departure_trees[0]
        
        try:
            # Remover de la estación
            self.docked_vehicles.remove(vehicle)
            
            # Agregar al árbol de salida
            success = departure_tree.add_vehicle(vehicle)
            if not success:
                print(f"ERROR No se pudo agregar vehículo {vehicle.vehicle_id} al árbol de salida")
                # Revertir - volver a agregar a docked
                self.docked_vehicles.append(vehicle)
                return False
                
            vehicle.current_track = departure_tree
            vehicle.state = "accelerating_down"
            
   
            return True
            
        except Exception as e:
            print(f"ERROR: en salida de vehículo {vehicle.vehicle_id}: {e}")
            return False

    def receive_vehicle(self, vehicle, arrival_tree):
        """
        RECIBE UN VEHÍCULO QUE LLEGA A TRAVÉS DE UN ÁRBOL DE LLEGADA
        MEJORADO: Validaciones mejoradas
        """
        if arrival_tree not in self.arrival_trees:
            print(f"ERROR: Árbol {arrival_tree.track_id} no pertenece a estación {self.name}")
            return False
        
        # Remover del árbol de llegada
        arrival_tree.remove_vehicle(vehicle)
        
        # Dockear en la estación
        success = self.dock_vehicle(vehicle)
        
        if not success:
            print(f"ERROR: No se pudo recibir vehículo {vehicle.vehicle_id} en {self.name}")
        
        return success

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
            "docked_vehicles": len(self.docked_vehicles),
            "capacity": self.capacity,
            "arrival_trees": [tree.track_id for tree in self.arrival_trees],
            "departure_trees": [tree.track_id for tree in self.departure_trees],
            "vehicle_ids": [v.vehicle_id for v in self.docked_vehicles],
            "status": "FULL" if len(self.docked_vehicles) >= self.capacity else "AVAILABLE",
            "tree_selector_configured": self.tree_selector is not None,
            "arrival_capacity": capacity_info
        }
        
        # Agregar información de árboles si hay TreeSelector
        if self.tree_selector and self.arrival_trees:
            trees_status = self.tree_selector.get_trees_status(self.arrival_trees)
            info["trees_status"] = trees_status
            
        return info

    def get_docked_vehicles_info(self):
        """
        Retorna información detallada de los vehículos docked (sin cambios)
        """
        vehicles_info = []
        for vehicle in self.docked_vehicles:
            vehicle_info = {
                "vehicle_id": vehicle.vehicle_id,
                "state": vehicle.state,
                "destination": vehicle.destination_station,
                "passengers": vehicle.passengers,
                "capacity": vehicle.capacity
            }
            vehicles_info.append(vehicle_info)
        return vehicles_info

    def find_vehicle_by_id(self, vehicle_id):
        """
        Busca un vehículo docked por su ID (sin cambios)
        """
        for vehicle in self.docked_vehicles:
            if vehicle.vehicle_id == vehicle_id:
                return vehicle
        return None

    def update(self, brain, dt):
        """
        Actualiza el estado de la estación (para ser llamado cada frame)
        MEJORADO: Incluye procesamiento de salidas
        """
        self.process_departures(brain)

    # ========== MÉTODOS DE CONFIGURACIÓN ==========

    def set_capacity(self, new_capacity):
        """Cambia la capacidad de la estación (sin cambios)"""
        old_capacity = self.capacity
        self.capacity = new_capacity

    def assign_destination_to_vehicle(self, vehicle_id, destination_station_id):
        """
        Asigna un destino a un vehículo específico en la estación (sin cambios)
        """
        vehicle = self.find_vehicle_by_id(vehicle_id)
        if not vehicle:
            print(f"ERROR: Vehículo {vehicle_id} no encontrado en estación {self.name}")
            return False
        
        return self.undock_vehicle(vehicle, destination_station_id)