import math


class Vector3:                                                      # Da un punto en 3 dimeniones
    def __init__(self, x=0.0, y=0.0, z=0.0):                        # Inicialisador de la clase
        self.x = x      # Cordenada eje x
        self.y = y      # Cordenada eje y
        self.z = z      # Cordenada eje z
    
    def __add__(self, other):                                       # Suma de dos cordenadas en 3D (Retorna vector)
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other):                                       # Resta de dos cordenadas en 3D (Retorna vector)
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)
    
    def __mul__(self, scalar):                                      # Multiplicacion de la cordenada completa por un escalar (Retorna vector)
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)
    
    def length(self):                                               # Distancia entre el cento (0,0,0) y el punto inicialisado (Retorna escalar)
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)
    
    def normalize(self):                                            # Normalisacion de el vector formado (entrega la direccion del vector)
        length = self.length()
        if length > 0:
            return Vector3(self.x / length, self.y / length, self.z / length)
        return Vector3()
    
    def to_tuple(self):                                             # retorna las cordenadas como tupla
        return (self.x, self.y, self.z)