from objects.passenger import Passenger
from objects.acceleration_tree import AccelerationTree

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
        self.passengers = {}  # passenger_id -> Passenger
        self.simulation_time = 0.0
        self.passenger_counter = 0  # Contador para asignar IDs únicos a pasajeros

    def generate_passenger(self, origin_station_id, destination_station_id, mobility=1):
        """Genera un nuevo pasajero en el sistema"""
        self.passenger_counter += 1
        passenger_id = f"P{self.passenger_counter}"
        
        passenger = Passenger(passenger_id, origin_station_id, destination_station_id, mobility)
        self.passengers[passenger_id] = passenger
        
        # Agregar pasajero a la estación de origen
        origin_station = self.stations.get(origin_station_id)
        if origin_station:
            origin_station.add_passenger(passenger)
        
        print(f"Pasajero {passenger_id} generado: {origin_station_id} -> {destination_station_id}")
        return passenger

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
        

        # DEBUG: Imprimir información de ruta
        print(f"DEBUG RUTA: Vehículo {vehicle.vehicle_id}")
        print(f"  Desde: Estación {from_station.station_id} ({from_station.name})")
        print(f"  Hacia: Estación {to_station.station_id} ({to_station.name})")
        print(f"  Target Trees: {target_trees}")
        
        # Mostrar árboles de llegada de la estación destino
        station = self.stations.get(to_station.station_id)
        if station:
            print(f"  Árboles de llegada en {station.name}: {[tree.track_id for tree in station.arrival_trees]}")



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
        
        # 2. procesar solicitudes de pasajeros
        self.update_passenger_requests()

        # 3. Actualizar pasajeros
        self._update_passengers(dt)

        # 4. Actualizar estaiciones
        for station in self.stations.values():
            station.update_lanes(dt)

        # 5. Procesar transiciones entre tracks
        self._handle_track_transitions()
        
        # 6. Procesar operaciones en estaciones
        for station in self.stations.values():
            self._process_station_operations(station)

    def _update_passengers(self, dt):
        """Actualiza el estado de todos los pasajeros"""
        for passenger in self.passengers.values():
            passenger.update(dt)

    def handle_vehicle_request(self, station_id, passenger):
        """Maneja una solicitud de vehículo desde una estación"""
        # Buscar VMs vacíos o con capacidad en la red
        available_vehicles = self._find_available_vehicles_for_passenger(passenger)
        
        if available_vehicles:
            # Redirigir el primer VM disponible
            vehicle = available_vehicles[0]
            self._redirect_vehicle_to_station(vehicle, station_id, passenger)
            return True
        
        return False    

    def update_passenger_requests(self):
        """Procesa solicitudes de VMs para pasajeros en espera"""
        for station in self.stations.values():
            # Contar cuántos VMs están actualmente asignados a esta estación
            current_assignments = sum(1 for vehicle in self.vehicles.values() 
                                    if vehicle.destination_station == station.station_id)
            
            # Calcular cuántos VMs adicionales necesitamos
            needed_vehicles = len(station.waiting_passengers) - current_assignments
            
            if needed_vehicles > 0:
                print(f"🚨 Estación {station.station_id} necesita {needed_vehicles} VMs adicionales")
                
                # Solicitar VMs adicionales
                for _ in range(needed_vehicles):
                    available_vehicles = self._find_available_vehicles_for_station(station.station_id)
                    if available_vehicles:
                        vehicle = available_vehicles[0]  # Tomar el primer VM disponible
                        self._redirect_vehicle_to_station(vehicle, station.station_id)

    def _find_available_vehicles_for_station(self, station_id):
        """Encuentra VMs disponibles para una estación específica"""
        available_vehicles = []
        
        for vehicle in self.vehicles.values():
            # Verificar si el VM está disponible y no está ya asignado a otra estación
            if (vehicle.passengers < vehicle.capacity and 
                vehicle.state not in ["docked", "maintenance"] and
                vehicle.destination_station != station_id and  # No está ya asignado aquí
                self._can_vehicle_redirect(vehicle)):
                available_vehicles.append(vehicle)
        
        # Ordenar por proximidad a la estación (simplificado)
        available_vehicles.sort(key=lambda v: self._estimate_distance_to_station(v, station_id))
        
        print(f"🔍 VMs disponibles para estación {station_id}: {len(available_vehicles)}")
        return available_vehicles

    def _estimate_distance_to_station(self, vehicle, station_id):
        """Estima la distancia de un VM a una estación (simplificado)"""
        station = self.stations.get(station_id)
        if not station or not vehicle.current_position:
            return float('inf')
        
        # Estimación simple basada en posición actual
        return vehicle.current_position.distance_to(station.position)

    def _find_available_vehicles_for_passenger(self, passenger):
        """Encuentra VMs disponibles para un pasajero"""
        available_vehicles = []
        
        for vehicle in self.vehicles.values():
            # Verificar si el VM tiene capacidad y puede redirigirse
            if (vehicle.passengers < vehicle.capacity and 
                vehicle.state not in ["docked", "maintenance"] and
                self._can_vehicle_redirect(vehicle)):
                available_vehicles.append(vehicle)
        
        # Si no hay VMs con capacidad, buscar VMs vacíos
        if not available_vehicles:
            for vehicle in self.vehicles.values():
                if (vehicle.passengers == 0 and 
                    vehicle.state not in ["docked", "maintenance"] and
                    self._can_vehicle_redirect(vehicle)):
                    available_vehicles.append(vehicle)
        
        print(f"🔍 VMs disponibles para pasajero {passenger.id}: {len(available_vehicles)}")
        return available_vehicles

    def _redirect_vehicle_to_station(self, vehicle, station_id):
        """Redirige un vehículo a una estación para recoger pasajeros"""
        # Establecer nuevo destino
        vehicle.destination_station = station_id
        
        # Calcular nueva ruta
        target_trees = self._find_target_acceleration_trees(station_id)
        vehicle.target_acceleration_trees = target_trees
        
        print(f"🚗 VM {vehicle.vehicle_id} redirigido a estación {station_id}")

    def _can_vehicle_redirect(self, vehicle):
        """Verifica si un vehículo puede redirigirse"""
        # Un vehículo puede redirigirse si no está en un árbol de subida
        # o si está lo suficientemente lejos de otros vehículos
        if (vehicle.current_track and 
            isinstance(vehicle.current_track, AccelerationTree) and 
            vehicle.current_track.direction == "up"):
            return self._check_safe_distance(vehicle)
        
        return True

    def _check_safe_distance(self, vehicle):
        """Verifica distancia segura con otros vehículos en el mismo árbol"""
        current_track = vehicle.current_track
        if not current_track or not isinstance(current_track, AccelerationTree):
            return True
        
        # Verificar distancia con otros vehículos en el mismo árbol
        for other_vehicle_id, vehicle_data in current_track.vehicles.items():
            if other_vehicle_id != vehicle.vehicle_id:
                other_progress = vehicle_data['progress']
                current_progress = current_track.get_vehicle_progress(vehicle)
                
                # Reducir distancia mínima segura: 0.05 (5% del árbol)
                if abs(other_progress - current_progress) < 0.05:
                    print(f"⚠️  VM {vehicle.vehicle_id} muy cerca de VM {other_vehicle_id}, buscando otro árbol")
                    return False
        
        return True

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