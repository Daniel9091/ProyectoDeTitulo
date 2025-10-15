class Lane:
    def __init__(self, id: int, belt_speed: float, direction: str, station_connector_id: int):
        self.id = id
        self.belt_speed = belt_speed
        self.direction = direction  # "entry" or "exit"
        self.station_connector_id = station_connector_id
        self.passengers = []  # Lista de pasajeros en el carril
        self.vehicles = []    # Lista de VMs que están pasando
        self.active = True
        self.length = 10.0  # Longitud del carril en metros (para visualización)
        
    def activate(self):
        self.active = True
    
    def deactivate(self):
        self.active = False
    
    def add_passenger(self, passenger):
        """Agrega un pasajero al carril"""
        if self.active and passenger.state == "on_lane":
            passenger.assigned_lane_id = self.id
            passenger.position_on_lane = 0.0
            self.passengers.append(passenger)
            return True
        return False
    
    def remove_passenger(self, passenger):
        """Remueve un pasajero del carril"""
        if passenger in self.passengers:
            self.passengers.remove(passenger)
            return True
        return False
    
    def add_vehicle(self, vehicle):
        """Agrega un VM al carril (cuando pasa por el StationConnector adyacente)"""
        if vehicle not in self.vehicles:
            self.vehicles.append(vehicle)
            return True
        return False
    
    def remove_vehicle(self, vehicle):
        """Remueve un VM del carril"""
        if vehicle in self.vehicles:
            self.vehicles.remove(vehicle)
            return True
        return False
    
    def update_passengers(self, dt):
        """Actualiza la posición de los pasajeros en el carril"""
        for passenger in self.passengers[:]:  # Usar copia para poder remover
            passenger.move_on_lane(dt, self.belt_speed)
            
            # Si el pasajero está listo para abordar, intentar subirlo a un VM
            if passenger.state == "ready_to_board" and self.vehicles:
                for vehicle in self.vehicles:
                    if passenger.should_board_vehicle(vehicle):
                        if passenger.board_vehicle(vehicle):
                            self.remove_passenger(passenger)
                            break
    
    def get_lane_info(self):
        """Retorna información del carril"""
        return {
            "id": self.id,
            "direction": self.direction,
            "belt_speed": self.belt_speed,
            "active": self.active,
            "passenger_count": len(self.passengers),
            "vehicle_count": len(self.vehicles),
            "passengers": [p.get_passenger_info() for p in self.passengers],
            "vehicles": [v.vehicle_id for v in self.vehicles]
        }