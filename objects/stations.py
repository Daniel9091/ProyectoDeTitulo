from objects.base import Vector3

class Station:
    """
    ESTACIÓN FÍSICA DEL SISTEMA DE TRANSPORTE
    
    Responsabilidades (Primera Etapa):
    - Gestionar vehículos docked (estacionados)
    - Administrar árboles de aceleración de llegada y salida
    - Asignar destinos manualmente a los VMs (sin pasajeros por ahora)
    - Coordinar transiciones entre estación y red de vías
    
    Características:
    - No considera pasajeros ni andenes (lanes) en esta etapa
    - Asignación manual de destinos a VMs
    - Gestión de árboles de aceleración para entrada/salida
    """

    def __init__(self, station_id, name, position):
        self.station_id = station_id
        self.name = name
        self.position = position  # Vector3 - posición en superficie
        self.arrival_trees = []   # Lista de AccelerationTree (dirección 'up')
        self.departure_trees = [] # Lista de AccelerationTree (dirección 'down')
        self.docked_vehicles = [] # Lista de ModularVehicle estacionados
        self.capacity = 10  # Capacidad máxima de vehículos docked
        
    def add_arrival_tree(self, acceleration_tree):
        """
        Agrega un árbol de aceleración de LLEGADA a la estación
        
        Args:
            acceleration_tree: Instancia de AccelerationTree con dirección 'up'
        """
        if acceleration_tree.direction != 'up':
            raise ValueError("Los árboles de llegada deben tener dirección 'up'")
        
        self.arrival_trees.append(acceleration_tree)
        print(f"Árbol de llegada {acceleration_tree.track_id} agregado a estación {self.name}")
    
    def add_departure_tree(self, acceleration_tree):
        """
        Agrega un árbol de aceleración de SALIDA de la estación
        
        Args:
            acceleration_tree: Instancia de AccelerationTree con dirección 'down'
        """
        if acceleration_tree.direction != 'down':
            raise ValueError("Los árboles de salida deben tener dirección 'down'")
        
        self.departure_trees.append(acceleration_tree)
        print(f"Árbol de salida {acceleration_tree.track_id} agregado a estación {self.name}")
    
    def dock_vehicle(self, vehicle):
        """
        Estaciona un vehículo en la estación (llegada)
        
        Args:
            vehicle: Instancia de ModularVehicle
        """
        if len(self.docked_vehicles) >= self.capacity:
            print(f"ERROR: Estación {self.name} está a capacidad máxima")
            return False
        
        if vehicle not in self.docked_vehicles:
            self.docked_vehicles.append(vehicle)
            vehicle.current_station = self.station_id
            vehicle.state = "docked"
            vehicle.current_track = None
            vehicle.destination_station = None  # Reset destino al llegar
            vehicle.target_acceleration_trees = []  # Limpiar ruta
            
            print(f"Vehículo {vehicle.vehicle_id} docked en estación {self.name}")
            return True
        return False
    
    def undock_vehicle(self, vehicle, destination_station_id):
        """
        Prepara un vehículo para salir de la estación con un destino
        
        Args:
            vehicle: Instancia de ModularVehicle
            destination_station_id: ID de la estación destino
            
        Returns:
            bool: True si se pudo preparar para salir, False en caso contrario
        """
        if vehicle not in self.docked_vehicles:
            print(f"ERROR: Vehículo {vehicle.vehicle_id} no está en estación {self.name}")
            return False
        
        if not self.departure_trees:
            print(f"ERROR: Estación {self.name} no tiene árboles de salida")
            return False
        
        # Asignar destino al vehículo
        vehicle.destination_station = destination_station_id
        vehicle.state = "ready_to_depart"
        
        print(f"Vehículo {vehicle.vehicle_id} preparado para salir de {self.name} hacia estación {destination_station_id}")
        return True
    
    def process_departures(self, brain):
        """
        Procesa los vehículos listos para salir y los envía a los árboles de salida
        
        Args:
            brain: Instancia de Brain para obtener rutas
        """
        vehicles_to_depart = []
        
        # Identificar vehículos listos para salir
        for vehicle in self.docked_vehicles:
            if vehicle.state == "ready_to_depart" and vehicle.destination_station:
                vehicles_to_depart.append(vehicle)
        
        # Procesar salidas
        for vehicle in vehicles_to_depart:
            self._depart_vehicle(vehicle, brain)
    
    def _depart_vehicle(self, vehicle, brain):
        """
        Envía un vehículo desde la estación a un árbol de salida
        
        Args:
            vehicle: Instancia de ModularVehicle
            brain: Instancia de Brain para calcular ruta
        """
        if not self.departure_trees:
            return
        
        # Calcular ruta usando Brain
        target_trees = brain.find_route(self.station_id, vehicle.destination_station)
        vehicle.target_acceleration_trees = target_trees
        
        # Seleccionar árbol de salida (por simplicidad, el primero)
        departure_tree = self.departure_trees[0]
        
        # Remover de la estación
        self.docked_vehicles.remove(vehicle)
        
        # Agregar al árbol de salida
        departure_tree.add_vehicle(vehicle)
        vehicle.current_track = departure_tree
        vehicle.state = "accelerating_down"
        
        print(f"Vehículo {vehicle.vehicle_id} partió de {self.name} hacia estación {vehicle.destination_station}")
        print(f"  Buscará árboles: {target_trees}")
    
    def receive_vehicle(self, vehicle, arrival_tree):
        """
        Recibe un vehículo que llega a través de un árbol de llegada
        
        Args:
            vehicle: Instancia de ModularVehicle
            arrival_tree: AccelerationTree por el que llegó el vehículo
        """
        if arrival_tree not in self.arrival_trees:
            print(f"ERROR: Árbol {arrival_tree.track_id} no pertenece a estación {self.name}")
            return False
        
        # Remover del árbol de llegada
        arrival_tree.remove_vehicle(vehicle)
        
        # Dockear en la estación
        success = self.dock_vehicle(vehicle)
        
        if success:
            print(f"Vehículo {vehicle.vehicle_id} recibido en {self.name} desde árbol {arrival_tree.track_id}")
        else:
            print(f"ERROR: No se pudo recibir vehículo {vehicle.vehicle_id} en {self.name}")
        
        return success
    
    def get_available_departure_tree(self):
        """
        Obtiene un árbol de salida disponible (con capacidad)
        
        Returns:
            AccelerationTree o None si no hay disponibles
        """
        for tree in self.departure_trees:
            # Por ahora, asumimos que todos tienen capacidad
            # En el futuro podríamos verificar la cantidad de vehículos en el árbol
            return tree
        return None
    
    def get_station_info(self):
        """
        Retorna información completa de la estación
        """
        return {
            "station_id": self.station_id,
            "name": self.name,
            "position": self.position.to_tuple(),
            "docked_vehicles": len(self.docked_vehicles),
            "capacity": self.capacity,
            "arrival_trees": [tree.track_id for tree in self.arrival_trees],
            "departure_trees": [tree.track_id for tree in self.departure_trees],
            "vehicle_ids": [v.vehicle_id for v in self.docked_vehicles],
            "status": "FULL" if len(self.docked_vehicles) >= self.capacity else "AVAILABLE"
        }
    
    def get_docked_vehicles_info(self):
        """
        Retorna información detallada de los vehículos docked
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
    
    def set_capacity(self, new_capacity):
        """
        Cambia la capacidad de la estación
        """
        old_capacity = self.capacity
        self.capacity = new_capacity
        print(f"Capacidad de estación {self.name} cambiada de {old_capacity} a {new_capacity}")
    
    def has_available_capacity(self):
        """
        Verifica si la estación tiene capacidad disponible
        """
        return len(self.docked_vehicles) < self.capacity
    
    def find_vehicle_by_id(self, vehicle_id):
        """
        Busca un vehículo docked por su ID
        
        Returns:
            ModularVehicle o None si no se encuentra
        """
        for vehicle in self.docked_vehicles:
            if vehicle.vehicle_id == vehicle_id:
                return vehicle
        return None

    def update(self, brain, dt):
        """
        Actualiza el estado de la estación (para ser llamado cada frame)
        
        Args:
            brain: Instancia de Brain para procesar salidas
            dt: Delta time (no utilizado directamente por ahora)
        """
        self.process_departures(brain)
    
    def assign_destination_to_vehicle(self, vehicle_id, destination_station_id):
        """
        Asigna un destino a un vehículo específico en la estación
        
        Args:
            vehicle_id: ID del vehículo
            destination_station_id: ID de la estación destino
            
        Returns:
            bool: True si se pudo asignar, False en caso contrario
        """
        vehicle = self.find_vehicle_by_id(vehicle_id)
        if not vehicle:
            print(f"ERROR: Vehículo {vehicle_id} no encontrado en estación {self.name}")
            return False
        
        return self.undock_vehicle(vehicle, destination_station_id)