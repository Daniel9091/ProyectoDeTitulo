class Passenger:
    def __init__(self, id: int, origin_station_id: str, destination_station_id: str, mobility: int = 1):
        self.id = id
        self.origin_station_id = origin_station_id
        self.destination_station_id = destination_station_id
        self.mobility = mobility
        
        # Estados del pasajero
        self.state = "waiting"  # waiting, in_queue, on_lane, boarding, in_vehicle, arrived
        self.current_station_id = origin_station_id
        self.assigned_vehicle_id = None
        self.assigned_lane_id = None
        self.position_in_station = None  # Posición en la estación (para visualización)
        self.position_on_lane = 0.0  # Progreso en el lane (0-1)
        self.waiting_time = 0.0
        self.total_travel_time = 0.0
        
        # Tiempos de seguimiento
        self.arrival_time = None
        self.boarding_time = None
        self.departure_time = None
        
    def update(self, dt):
        """Actualiza el estado del pasajero"""
        if self.state in ["waiting", "in_queue"]:
            self.waiting_time += dt
        elif self.state == "in_vehicle":
            self.total_travel_time += dt
    
    def assign_to_lane(self, lane_id):
        """Asigna el pasajero a un andén específico"""
        self.assigned_lane_id = lane_id
        self.state = "on_lane"
        self.position_on_lane = 0.0
    
    def board_vehicle(self, vehicle):
        """El pasajero aborda un vehículo"""
        if vehicle.add_passenger(self):
            self.assigned_vehicle_id = vehicle.vehicle_id
            self.state = "in_vehicle"
            self.boarding_time = self.total_travel_time + self.waiting_time
            return True
        return False
    
    def exit_vehicle(self, station_id):
        """El pasajero sale del vehículo en una estación"""
        self.state = "arrived"
        self.current_station_id = station_id
        self.assigned_vehicle_id = None
        self.departure_time = self.total_travel_time + self.waiting_time
    
    def move_on_lane(self, dt, lane_speed):
        """Mueve al pasajero a lo largo del lane"""
        if self.state == "on_lane":
            self.position_on_lane += dt * lane_speed
            if self.position_on_lane >= 1.0:
                self.position_on_lane = 1.0
                self.state = "ready_to_board"
    
    def get_passenger_info(self):
        """Retorna información del pasajero"""
        return {
            "id": self.id,
            "state": self.state,
            "origin": self.origin_station_id,
            "destination": self.destination_station_id,
            "current_station": self.current_station_id,
            "assigned_vehicle": self.assigned_vehicle_id,
            "assigned_lane": self.assigned_lane_id,
            "waiting_time": self.waiting_time,
            "travel_time": self.total_travel_time,
            "position_on_lane": self.position_on_lane
        }
    
    def is_waiting_for_vehicle(self):
        """Verifica si el pasajero está esperando un vehículo"""
        return self.state in ["waiting", "in_queue", "on_lane", "ready_to_board"]
    
    def should_board_vehicle(self, vehicle):
        """Determina si el pasajero puede abordar un vehículo específico"""
        if self.state != "ready_to_board":
            return False
        
        # Verificar que el vehículo va a la estación destino del pasajero
        if vehicle.destination_station != self.destination_station_id:
            return False
            
        # Verificar que el vehículo tiene capacidad
        if vehicle.passengers >= vehicle.capacity:
            return False
            
        return True