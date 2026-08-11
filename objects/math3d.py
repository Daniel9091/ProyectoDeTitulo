"""Operaciones de álgebra vectorial 3D para el posicionamiento de objetos en NSim."""
import math

class Vector3:
    """
    Manejo de vectores 3D
    Operaciones matematicas de vectores 3D
    """

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = x
        self.y = y 
        self.z = z

    def __add__(self, other):
        """Suma vectores"""
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other):
        """Resta vectores"""
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __neg__(self):
        """Negativo de un vector"""
        return Vector3(-self.x, -self.y, -self.z)

    def __mul__(self, escalar):
        """Multiplicación por escalar"""
        return Vector3(self.x * escalar, self.y * escalar, self.z * escalar)
    
    def __truediv__(self, escalar):
        """Division por escalar"""
        return Vector3(self.x / escalar, self.y / escalar, self.z / escalar)

    def __hash__(self):
        """Hash de un vector"""
        return hash((round(self.x, 9), round(self.y, 9), round(self.z, 9)))

    def __eq__(self, other):
        """Compara si dos vectores son iguales con una tolerancia para números float"""
        if not isinstance(other, Vector3):
            return NotImplemented
        return ((abs(self.x-other.x) < 1e-9) and 
                (abs(self.y-other.y) < 1e-9) and 
                (abs(self.z-other.z) < 1e-9))

    def __str__(self):
        """Muestra el valor del vector"""
        return f"({self.x}, {self.y}, {self.z})"

    def __repr__(self):
        """Muestra el valor del vector"""
        return f"Vector3({self.x}, {self.y}, {self.z})"

    def length(self):
        """Calcula la longitud del vector"""
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)
    
    def normalize(self):
        """
        Normaliza el vector:
        Representa la dirección como vector unitario
        """
        length = self.length()
        if length > 0:
            return Vector3(self.x / length, self.y / length, self.z / length)
        return Vector3()
    
    def dot(self, other):
        """Producto punto entre dos vectores"""
        return self.x * other.x + self.y * other.y + self.z * other.z

    def distance_to(self,other):
        """Distancia entre este vector y otro"""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2 + (self.z - other.z)**2)

    def to_tuple(self):
        """Retorna el vector como tupla (x, y, z)."""
        return (self.x, self.y, self.z)


