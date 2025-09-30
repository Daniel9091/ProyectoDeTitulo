class Lane:
    def __init__(self, id: int, belt_speed: float, direction: str):         # Representa un anden de embarque dentro de una estacion
        self.id = id                            # Identificador uniico  de anden
        self.belt_speed = belt_speed            # Velocidad que tiene la correa tranportadora de gente que sube a un VM
        self.direction = direction              # "entry" or "exit" (Carril de entrada o de salida)
        self.vehicles = []                      # Lista de VM que estan pasando por al lado de la cinta
        self.active = True                      # Carril abilitado o desabilitado en la estacion (depende de la cantidad de personas en estacion)
    
    def activate(self):                         # Activa carril
        self.active = True
    
    def deactivate(self):                       # Desactiva carril
        self.active = False
    
    def add_vehicle(self, vehicle):             # A la llegada de un nuevo VM se añade a lista de VM que estan en la cinta
        if self.active:
            self.vehicles.append(vehicle)
            return True
        return False
    
    def remove_vehicle(self, vehicle):          # VM debe ser eliminado de la cinta una vez que ya se halla movido por ese lugar
        if vehicle in self.vehicles:
            self.vehicles.remove(vehicle)
            return True
        return False



##### Notas Clase #####

# 1.
# No me hace mucho sentido la direccion del carril (entrada o salida) 
# (A lo mejor cuando llegue un VM debe tener un lapso donde se baje la gente y luego un lapso para que se suba la gente)
# (v1)

# 2.
# Me guta la idea de que esta banda sea al mismo tiempo una banda transportadora de gente como el carril que nesesita un VM
# Para moverse dentro de la estacion

# 3.
# Falta funcion de movimiento para VM durante la cinta
# (v1)
