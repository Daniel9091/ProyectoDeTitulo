import pygame
from ui.info_panel import draw_info_panel
import math

class Renderer:
    def __init__(self, screen, camera):                                                         # Inisialisacion de el renderizador con la camara 
        self.screen = screen                                                                    # Superficie de Pygame donde se dibujara iniciada
        self.camera = camera                                                                    # Camara que maneja la proyeccion 3D a 2D
    
    def draw(self, simulation):                                                                 # Dibuja todos los elementeos de la simulacion con todos los objetos de la simulacion
        self.screen.fill((20, 20, 30))                                                          # Color oscuro
        
        # Dibujar conexiones entre estaciones (conectores)
        self.draw_connectors(simulation.connectors)

        # Dibujar estaciones
        for station in simulation.stations:
            self.draw_station(station)

        # Dibujar vehículos
        for vehicle in simulation.vehicles:
            self.draw_vehicle(vehicle)

        # dibujar información de depuración (estaciones, vehiculos, arboles)
        self.draw_debug_info(simulation)
        
        # Dibujar UI si esta activado
        if simulation.show_info:
            draw_info_panel(self.screen, simulation, self.camera)
    
    def draw_connectors(self, connectors):                                                      # Dibuja conectores entre estaciones
        """Dibuja los conectores entre estaciones"""
        for connector in connectors:
            # Dibujar línea entre estaciones
            start_pos = connector.origin_station.position                                      # ESTO DEBE CAMBIAR EN UN FUTURO (DEBE SER POR PUNTO ARBITRARIO NO SOLO ESTACIONES)
            end_pos = connector.destination_station.position
            start_2d = self.camera.project_3d_to_2d((start_pos.x, start_pos.y, start_pos.z))
            end_2d = self.camera.project_3d_to_2d((end_pos.x, end_pos.y, end_pos.z))
            if start_2d and end_2d:
                pygame.draw.line(self.screen, (0, 255, 0), start_2d, end_2d, 2)
                
                # Arboles de aceleracion
                for tree in connector.acceleration_trees:
                    self.draw_acceleration_tree(tree)
    
    def draw_acceleration_tree(self, tree):                                                     # Dibuja un árbol de aceleración con colores según el tipo"""
        
        # Calcular puntos a lo largo del árbol
        points = []
        slope_rad = math.radians(tree.slope)
        
        # Más puntos para una línea más suave
        for i in range(20):
            progress = i / 19.0
            distance = tree.length * progress                                                   # NO ME GUSTA EL ATRIBUTO LENGH
            
            x = tree.position.x + distance * math.cos(slope_rad)
            z = tree.position.z + distance * math.sin(slope_rad)
            
            point_2d = self.camera.project_3d_to_2d((x, 0, z))
            if point_2d:
                points.append(point_2d)
        
        # Dibujar línea que representa el árbol con color según el tipo
        if len(points) > 1:
            if tree.type == "acceleration":
                color = (255, 100, 100)  # Rojo para aceleración
                thickness = 3
            elif tree.type == "deceleration":
                color = (100, 100, 255)  # Azul para desaceleración
                thickness = 3
            else:  # constant
                color = (100, 255, 100)  # Verde para velocidad constante
                thickness = 2
            
            pygame.draw.lines(self.screen, color, False, points, thickness)
            
            # Dibujar punto al inicio y final del árbol
            if points:
                pygame.draw.circle(self.screen, color, points[0], 4)
                pygame.draw.circle(self.screen, color, points[-1], 4)
    
    def draw_station(self, station):
        """Dibuja una estación como prismas rectangulares de 3 pisos SUPERPUESTOS"""
        # Dimensiones de la estación (ancho, largo, altura por piso)
        width = 30  # metros de ancho
        length = 60  # metros de largo
        floor_height = 5  # altura de cada piso
        floor_spacing = 6  # espacio vertical entre pisos
        
        # Posición de la estación (coordenadas del centro del piso superior)
        center_x, center_y, top_z = station.position.x, station.position.y, station.position.z
        
        # Definir y dibujar cada uno de los 3 pisos
        for floor_level in range(3):
            # Calcular la altura Z de este piso (cada piso está más abajo)
            floor_z = top_z - (floor_level * floor_spacing)
            
            # Calcular las coordenadas de los 8 vértices para ESTE piso
            half_width = width / 2
            half_length = length / 2
            
            vertices = [
                # Cara superior (techo del piso)
                (center_x - half_width, center_y - half_length, floor_z),
                (center_x + half_width, center_y - half_length, floor_z),
                (center_x + half_width, center_y + half_length, floor_z),
                (center_x - half_width, center_y + half_length, floor_z),
                
                # Cara inferior (piso del piso)
                (center_x - half_width, center_y - half_length, floor_z - floor_height),
                (center_x + half_width, center_y - half_length, floor_z - floor_height),
                (center_x + half_width, center_y + half_length, floor_z - floor_height),
                (center_x - half_width, center_y + half_length, floor_z - floor_height)
            ]
            
            # Proyectar vértices a 2D
            vertices_2d = []
            for v in vertices:
                projected = self.camera.project_3d_to_2d(v)
                if projected:
                    vertices_2d.append(projected)
            
            # Color diferente para cada piso para distinguirlos
            floor_colors = [
                (200, 150, 100),   # Piso 0 - superficie (marrón claro)
                (150, 150, 200),   # Piso 1 - vestíbulo (azul claro) 
                (200, 100, 100)    # Piso 2 - andenes (rojo claro)
            ]
            
            # Dibujar las caras del prisma para este piso
            if len(vertices_2d) >= 8:
                color = floor_colors[floor_level]
                
                # Cara superior (techo)
                pygame.draw.polygon(self.screen, color, 
                                [vertices_2d[0], vertices_2d[1], vertices_2d[2], vertices_2d[3]], 1)
                
                # Cara inferior (piso)
                pygame.draw.polygon(self.screen, color, 
                                [vertices_2d[4], vertices_2d[5], vertices_2d[6], vertices_2d[7]], 1)
                
                # Caras laterales
                for i in range(4):
                    # Conectar vértices superiores e inferiores (paredes verticales)
                    pygame.draw.line(self.screen, color, vertices_2d[i], vertices_2d[i+4], 1)
                    
                    # Conectar vértices adyacentes en la misma cara
                    next_i = (i + 1) % 4
                    pygame.draw.line(self.screen, color, vertices_2d[i], vertices_2d[next_i], 1)
                    pygame.draw.line(self.screen, color, vertices_2d[i+4], vertices_2d[next_i+4], 1)
  
    def draw_vehicle(self, vehicle):                                                    # Dibujo de un VM
        # Tamaño del vehículo
        size = 8
        half_size = size / 2
        
        # Posición del vehículo
        pos = vehicle.position
        vertices = [
            (pos.x - half_size, pos.y - half_size, pos.z - half_size),
            (pos.x + half_size, pos.y - half_size, pos.z - half_size),
            (pos.x + half_size, pos.y + half_size, pos.z - half_size),
            (pos.x - half_size, pos.y + half_size, pos.z - half_size),
            (pos.x - half_size, pos.y - half_size, pos.z + half_size),
            (pos.x + half_size, pos.y - half_size, pos.z + half_size),
            (pos.x + half_size, pos.y + half_size, pos.z + half_size),
            (pos.x - half_size, pos.y + half_size, pos.z + half_size)
        ]
        
        # Proyectar vértices a 2D
        vertices_2d = []
        for v in vertices:
            projected = self.camera.project_3d_to_2d(v)
            if projected:
                vertices_2d.append(projected)
        
        # Dibujar el cubo si tenemos suficientes puntos
        if len(vertices_2d) >= 8:
            color = (255, 0, 0)  # Rojo para vehículos
            
            # Cara frontal
            pygame.draw.polygon(self.screen, color, 
                            [vertices_2d[4], vertices_2d[5], vertices_2d[6], vertices_2d[7]], 1)
            
            # Cara trasera
            pygame.draw.polygon(self.screen, color, 
                            [vertices_2d[0], vertices_2d[1], vertices_2d[2], vertices_2d[3]], 1)
            
            # Conectar las caras
            for i in range(4):
                pygame.draw.line(self.screen, color, vertices_2d[i], vertices_2d[i+4], 1)
                next_i = (i + 1) % 4
                pygame.draw.line(self.screen, color, vertices_2d[i], vertices_2d[next_i], 1)
                pygame.draw.line(self.screen, color, vertices_2d[i+4], vertices_2d[next_i+4], 1)

    def draw_debug_info(self, simulation):                                              # Informacion de debug mostrada
        font = pygame.font.SysFont('Arial', 12)
        used_positions = []  # Lista para trackear posiciones ya usadas
        
        # Mostrar información de estaciones
        for i, station in enumerate(simulation.stations):
            text = font.render(f"S{station.id}: {station.name}", True, (0, 255, 0))
            pos_2d = self.camera.project_3d_to_2d((station.position.x, station.position.y + 15, station.position.z))
            
            if pos_2d and self._is_position_available(pos_2d, used_positions, text.get_size()):
                self.screen.blit(text, pos_2d)
                used_positions.append((pos_2d[0], pos_2d[1], text.get_width(), text.get_height()))
        
        # Mostrar información de vehículos
        for vehicle in simulation.vehicles:
            speed_color = (255, 255, 255)
            if vehicle.velocity > 15:
                speed_color = (255, 0, 0)
            elif vehicle.velocity > 10:
                speed_color = (255, 165, 0)
            elif vehicle.velocity > 5:
                speed_color = (255, 255, 0)
            
            info_lines = [
                f"V{vehicle.id}",
                f"Vel: {vehicle.velocity:.1f}m/s ({vehicle.velocity*3.6:.1f}km/h)",
                f"Estado: {vehicle.state}",
                f"Dist: {vehicle.distance_traveled_on_tree:.1f}m"
            ]
            
            if vehicle.current_connector:
                info_lines.append(f"Conector: {vehicle.current_connector.id}")
            if vehicle.destination_station:
                info_lines.append(f"Dest: S{vehicle.destination_station.id}")
            
            # Dibujar líneas de información del vehículo
            for i, line in enumerate(info_lines):
                color = speed_color if "Vel:" in line else (200, 200, 200)
                text = font.render(line, True, color)
                pos_2d = self.camera.project_3d_to_2d((
                    vehicle.position.x, 
                    vehicle.position.y + 5 + i * 12, 
                    vehicle.position.z
                ))
                
                if pos_2d and self._is_position_available(pos_2d, used_positions, text.get_size()):
                    self.screen.blit(text, pos_2d)
                    used_positions.append((pos_2d[0], pos_2d[1], text.get_width(), text.get_height()))
        
        # Mostrar información de árboles de aceleración
        for connector in simulation.connectors:
            for tree in connector.acceleration_trees:
                tree_info = f"Tree {tree.id}: {tree.type} {tree.slope}°"
                tree_pos_2d = self.camera.project_3d_to_2d((
                    tree.position.x + tree.length/2, 
                    tree.position.y + 10, 
                    tree.position.z
                ))
                
                if tree_pos_2d:
                    text = font.render(tree_info, True, (180, 180, 255))
                    if self._is_position_available(tree_pos_2d, used_positions, text.get_size()):
                        self.screen.blit(text, tree_pos_2d)
                        used_positions.append((tree_pos_2d[0], tree_pos_2d[1], text.get_width(), text.get_height()))

    def _is_position_available(self, pos_2d, used_positions, text_size, margin=2):      # Verifica si una posicion esta disponible par dibujar texto sin superponerse
        x, y = pos_2d                                                       # Posicion propuesta en 2d
        w, h = text_size                                                    # del texto
        new_rect = (x - margin, y - margin, w + 2*margin, h + 2*margin)     # El margen se ocupa para saber cuanta distancia se guarda
        
        for used in used_positions:                                         # Retorna True or False dependiendo de si se puede o no dibujar
            if (new_rect[0] < used[0] + used[2] and
                new_rect[0] + new_rect[2] > used[0] and
                new_rect[1] < used[1] + used[3] and
                new_rect[1] + new_rect[3] > used[1]):
                return False
        return True