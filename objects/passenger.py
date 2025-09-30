class Passenger:
    def __init__(self, id: int, origin_station_id: str, destination_station_id: str, mobility: int = 1):    # Generador de la clase
        self.id = id                                                # identificador unico
        self.origin_station_id = origin_station_id                  # En que estacion parte
        self.destination_station_id = destination_station_id        # A que estacion debe llegar
        self.in_transit = False                                     # El pasagero esta en transito (subido a algun VM?)
        self.assigned_vehicle_id = None                             # VM asignado
        self.mobility = mobility                                    # 1 = normal, 2 = reduced mobility, etc.
    
    def board_vehicle(self, vehicle):                               # Funcion para abordar un VM
        if vehicle.add_passenger(self):
            self.in_transit = True
            self.assigned_vehicle_id = vehicle.id
            return True
        return False
    
    def exit_vehicle(self):                                         # Fucnion para salir de un VM
        """Passenger exits the vehicle"""
        self.in_transit = False
        self.assigned_vehicle_id = None