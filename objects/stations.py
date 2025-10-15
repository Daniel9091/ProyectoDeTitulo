from objects.base import Vector3
from objects.lane import Lane

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
        
        # Componentes Fisicos
        self.arrival_trees = []     # Lista de AccelerationTree (dirección 'up')
        self.departure_trees = []   # Lista de AccelerationTree (dirección 'down')
        self.docked_vehicles = []   # Lista de ModularVehicle estacionados
        self.lanes = []             # Lista de Lane asociados a la estación    
        
        # Gestion de pasageros
        self.waiting_passengers = []  # Pasajeros esperando en la estación (no implementado aún)
        self.passenger_queue = []      # Cola de pasajeros para abordar (no implementado aún)
        self.arrived_passengers = []    # Pasajeros que han llegado (no implementado aún)

        # Configuración
        self.capacity = 10  # Capacidad máxima de vehículos docked
        self.max_queue_length = 50  # Longitud máxima de la cola de pasajeros (no implementado aún)

        # Estadisticas
        self.total_passengers_served = 0  # Total de pasajeros que han sido servidos (no implementado aún)
        self.avarage_wait_time = 0.0      # Tiempo promedio de espera de pasajeros (no implementado aún)

    def add_lane(self, lane_id, belt_speed, direction, station_connector_id):
        """ Agrega un anden  a la estacion"""
        lane = Lane(lane_id, belt_speed, direction, station_connector_id)
        self.lanes.append(lane)
        return lane

    def add_passenger(self, passenger):
        """Agrega un pasajero a la estación"""
        if len(self.waiting_passengers) < self.max_queue_length:
            passenger.current_station_id = self.station_id
            passenger.state = "in_queue"
            self.waiting_passengers.append(passenger)
            
            # Intentar asignar inmediatamente a un andén
            self._assign_passenger_to_lane(passenger)
            return True
        return False

    def process_passenger_assignments(self):
        """Asigna pasajeros en espera a andenes disponibles"""
        for passenger in self.waiting_passengers[:]:
            self._assign_passenger_to_lane(passenger)

    def _assign_passenger_to_lane(self, passenger):
        """Asigna un pasajero a un andén disponible"""
        available_lanes = self._get_available_lanes_for_destination(passenger.destination_station_id)
        
        for lane in available_lanes:
            if len(lane.passengers) < 8:  # Aumentar capacidad por andén
                passenger.assign_to_lane(lane.id)
                lane.add_passenger(passenger)
                if passenger in self.waiting_passengers:
                    self.waiting_passengers.remove(passenger)
                print(f"✅ Pasajero {passenger.id} asignado al andén {lane.id}")
                return True
        
        print(f"⚠️  No hay andenes disponibles para pasajero {passenger.id}")
        return False

    def _get_available_lanes_for_destination(self, destination_station_id):
        """Obtiene andenes disponibles para una estación destino"""
        available_lanes = []
        
        for lane in self.lanes:
            # Verificar si hay VMs en este lane que vayan al destino
            for vehicle in lane.vehicles:
                if vehicle.destination_station == destination_station_id and vehicle.passengers < vehicle.capacity:
                    available_lanes.append(lane)
                    break
                # Si no hay VMs actuales, el lane está disponible para nuevos VMs
                elif len(lane.vehicles) == 0:
                    available_lanes.append(lane)
                
        return available_lanes

    def _request_vehicle_for_passenger(self, passenger):
        """Solicita un VM vacío para un pasajero"""
        # Buscar VMs vacíos en la red que puedan redirigirse aquí
        # Esta lógica se coordinará con el Brain
        print(f"Estación {self.station_id} solicitando VM para pasajero {passenger.id} hacia estación {passenger.destination_station_id}")
        return True  # Por ahora siempre retorna éxito

    def process_vehicle_arrival(self, vehicle, arrival_tree):
        """Procesa la llegada de un vehículo a la estación"""
        # Desembarcar pasajeros
        disembarked_count = vehicle.disembark_passengers()
        
        # Actualizar estadísticas de pasajeros que llegaron
        for passenger in vehicle.passengers_info:
            if passenger.destination_station_id == self.station_id:
                passenger.exit_vehicle(self.station_id)
                self.arrived_passengers.append(passenger)
                self.total_passengers_served += 1
        
        # Remover del árbol de llegada
        arrival_tree.remove_vehicle(vehicle)
        
        # Dockear en la estación
        success = self.dock_vehicle(vehicle)
        
        if success:
            print(f"Vehículo {vehicle.vehicle_id} llegó a {self.name}. Pasajeros desembarcados: {disembarked_count}")
            
            # Asignar nuevos pasajeros a este VM si está disponible
            if vehicle.passengers < vehicle.capacity and self.waiting_passengers:
                self._assign_passengers_to_vehicle(vehicle)
        
        return success

    def _assign_passengers_to_vehicle(self, vehicle):
        """Asigna pasajeros a un vehículo disponible"""
        assigned_count = 0
        
        for passenger in self.waiting_passengers[:]:  # Copia para iterar seguramente
            if passenger.destination_station_id == vehicle.destination_station:
                if passenger.board_vehicle(vehicle):
                    self.waiting_passengers.remove(passenger)
                    assigned_count += 1
                    
                    if vehicle.passengers >= vehicle.capacity:
                        break
        
        if assigned_count > 0:
            print(f"Se asignaron {assigned_count} pasajeros al vehículo {vehicle.vehicle_id}")

    def update_lanes(self, dt):
        """Actualiza todos los andenes de la estación"""
        for lane in self.lanes:
            lane.update_passengers(dt)
            
            # Sincronizar VMs con StationConnectors
            self._sync_lane_vehicles(lane)

    def _sync_lane_vehicles(self, lane):
        """Sincroniza los VMs del lane con los StationConnectors"""
        # Esta función se conectará con la red para obtener VMs en el connector asociado
        pass

    def add_arrival_tree(self, acceleration_tree):
        """
        Agrega un árbol de aceleración de LLEGADA a la estación
        
        Args:
            acceleration_tree: Instancia de AccelerationTree con dirección 'up'
        """
        if acceleration_tree.direction != 'up':
            raise ValueError("Los árboles de llegada deben tener dirección 'up'")
        
        # ESTABLECER LA RELACIÓN BIDIRECCIONAL
        acceleration_tree.station_id = self.station_id
        
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
        
        # ESTABLECER LA RELACIÓN BIDIRECCIONAL
        acceleration_tree.station_id = self.station_id
        
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
        """Retorna información completa de la estación"""
        base_info = {
            "station_id": self.station_id,
            "name": self.name,
            "position": self.position.to_tuple(),
            "docked_vehicles": len(self.docked_vehicles),
            "capacity": self.capacity,
            "waiting_passengers": len(self.waiting_passengers),
            "passenger_queue": len(self.passenger_queue),
            "arrived_passengers": len(self.arrived_passengers),
            "total_passengers_served": self.total_passengers_served,
            "lanes": [lane.get_lane_info() for lane in self.lanes],
            "arrival_trees": [tree.track_id for tree in self.arrival_trees],
            "departure_trees": [tree.track_id for tree in self.departure_trees],
            "vehicle_ids": [v.vehicle_id for v in self.docked_vehicles]
        }
        
        return base_info
    
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