from objects.base import Vector3
import math

class StationConnector:
    def __init__(self, id: int, origin_station, destination_station, length: float, shape: str = "straight"):                   # Inicia objeto con sus atributos
        self.id = id                                        # Para poder reconocerlo
        self.origin_station = origin_station                # Estacion de origen que da el punto de partida para el conector 
        self.destination_station = destination_station      # Mismo comentario anterior
        self.length = length
        self.shape = shape                                  # "straight", "curve", etc. 
        self.acceleration_trees = []                        # Los arboles de acceleracion que se desprenden de la via
        self.vehicles = []
    
    def add_acceleration_tree(self, tree):                              # Añade arboles de aceleracion a la via
        self.acceleration_trees.append(tree)
    
    def calculate_trajectory(self, vehicle):                            # Calcula la trayectoria general del MV (arbol de acelaracion y via)
        """Calculate the trajectory through this connector"""
        trajectory = []
        
        # Add positions through each acceleration tree
        current_pos = vehicle.position
        for tree in self.acceleration_trees:
            # Calculate points along this tree
            points = self._calculate_tree_points(tree, current_pos)
            trajectory.extend(points)
            current_pos = points[-1] if points else current_pos
        
        return trajectory
    
    def _calculate_tree_points(self, tree, start_pos):                  # Calcula los puntos discretos a lo largo e un arbol de aceleracion
        points = []
        slope_rad = math.radians(tree.slope)                            # Combierte a radianes
        
        for i in range(10):                                             # 10 puntos equidistantes para cada arbol
            progress = i / 9.0
            distance = tree.length * progress                           # Progreso calculado con lenght

            # Calclo de la posicion 3D teniendo considerando la pendiente
            x = start_pos.x + distance * math.cos(slope_rad)
            z = start_pos.z + distance * math.sin(slope_rad)
            
            points.append(Vector3(x, start_pos.y, z))                   # Aca se añaden los puntos para el calculo (el z sin profundidad, y la distancia calculada con lenght)
        
        return points
    
    def update_vehicle_movement(self, vehicle, dt):                     # Actualiza movimiento dle vehiculo a travez del conector
        if not self.acceleration_trees:                                 # Retorna Falso si no hay arboles de aceleracion definidos
            return False
        
        # Movimiento a travezz de cada arbol de aceleracion en secuencia
        for tree in self.acceleration_trees:                        
            if not tree.execute_movement(vehicle, dt):
                return False                                            # Continua con el movimiento
        
        return True                                                     # Conector completado
    


# Siguente mejora:
# 0.
# agregar un atributo z que de la profundidad de la via





###### Notas importantes de la clase #####
# 1.
# para los atributos de estacion de origen y estacion final, podria ser buena idea combertirlos en vector inicial y final para no depender de las estaciones
# y poder controlar la altura en la que se encuentra la via (v2)

# 2.
# el lenght no se por que tiene que ser entregado, puede ser calculado segun la funcion o la resta de las distintas cordenadas (v2)

# 3.
# para tramos curbos el shape puede ser clave para definir si la funcion se va a comportar como una recta o como una curva (v3)

# 4.
# No me gusta que se calcule la trayectoria completa del MV aca, solo se debira calcular la trayectoria de el MV miettras este en esta via (v1)