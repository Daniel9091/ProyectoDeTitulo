from objects.station_connector import StationConnector

class BoardingLane(StationConnector):
    """
    ANDÉN DE EMBARQUE DENTRO DE UNA ESTACIÓN.
    
    Es un tipo especializado de StationConnector con una velocidad reducida
    y la capacidad de gestionar el embarque y desembarque de pasajeros.
    
    Un vehículo que se encuentre en este tipo de track NO es elegible
    para ser asignado a una nueva demanda de otra estación.
    """
    
    def __init__(self, track_id, start_pos, end_pos, speed=2.0):
        # Llama al constructor de la clase padre (StationConnector)
        super().__init__(track_id, start_pos, end_pos, speed)
        
        # Atributos específicos del andén
        self.is_boarding_platform = True # Flag explícito para facilitar comprobaciones
        self.passengers_waiting = [] # Futura implementación: cola de pasajeros esperando
        

    def get_track_type(self):
        """Sobrescribe el tipo de track para identificación."""
        return "BoardingLane"

    # Aquí irán en el futuro los métodos para gestionar pasajeros:
    # def allow_boarding(self, vehicle): ...
    # def manage_passenger_flow(self): ...