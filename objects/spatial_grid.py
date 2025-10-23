import collections

class SpatialGrid:
    """
    Una grilla espacial para optimizar la detección de colisiones.
    Divide el espacio en celdas y almacena objetos en ellas para reducir
    el número de comparaciones necesarias.
    """
    def __init__(self, cell_size):
        self.cell_size = cell_size
        self.grid = collections.defaultdict(list)

    def _get_cell_coords(self, position):
        """Calcula las coordenadas de la celda para una posición dada."""
        return (
            int(position.x // self.cell_size),
            int(position.y // self.cell_size),
            int(position.z // self.cell_size)
        )

    def clear(self):
        """Limpia la grilla para el siguiente frame."""
        self.grid.clear()

    def insert(self, obj):
        """Inserta un objeto en la grilla basado en su posición."""
        # Para simplificar, usamos el centro del objeto.
        # Una implementación más robusta podría insertar en múltiples celdas si el objeto las abarca.
        cell_coords = self._get_cell_coords(obj.current_position)
        self.grid[cell_coords].append(obj)

    def get_nearby(self, obj):
        """
        Obtiene una lista de objetos cercanos a un objeto dado, incluyendo los
        de la misma celda y las celdas vecinas.
        """
        nearby_objects = set()
        center_coords = self._get_cell_coords(obj.current_position)
        
        # Iterar sobre la celda central y sus 26 vecinas en 3D
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    cell_x = center_coords[0] + dx
                    cell_y = center_coords[1] + dy
                    cell_z = center_coords[2] + dz
                    
                    # Añadir objetos de la celda vecina al conjunto
                    # El uso de un `set` evita duplicados.
                    for nearby_obj in self.grid.get((cell_x, cell_y, cell_z), []):
                        # No añadir el objeto a su propia lista de vecinos
                        if nearby_obj.vehicle_id != obj.vehicle_id:
                            nearby_objects.add(nearby_obj)
                            
        return list(nearby_objects)