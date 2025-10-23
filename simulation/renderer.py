import pygame
from ui.info_panel import draw_info_panel
import math
from objects.base import Vector3

class Renderer:
    def __init__(self, screen, camera):
        self.screen = screen
        self.camera = camera
    
    def draw(self, simulation):
        self.screen.fill((20, 20, 30))
        
        # Dibujar todos los tracks de la red (conectores y árboles de aceleración)
        self.draw_network_tracks(simulation.network)
        
        # Dibujar estaciones
        for station in simulation.stations:
            self.draw_station(station)

        # Dibujar vehículos
        for vehicle in simulation.vehicles:
            self.draw_vehicle(vehicle)

        # Dibujar información de depuración
        self.draw_debug_info(simulation)
        
        # Dibujar UI si está activado
        if simulation.show_info:
            draw_info_panel(self.screen, simulation, self.camera)
    
    def draw_network_tracks(self, network):
        """Dibuja todos los tracks de la red (StationConnectors y AccelerationTrees)"""
        for track_id, track in network.tracks.items():
            if hasattr(track, 'get_track_type'):
                track_type = track.get_track_type()
                
                if track_type == "StationConnector":
                    self.draw_station_connector(track)
                elif track_type == "AccelerationTree":
                    self.draw_acceleration_tree(track)
                elif track_type == "BoardingLane":
                    self.draw_boarding_lane(track)
    
    def draw_station_connector(self, connector):
        """Dibuja un StationConnector como una línea recta"""
        start_2d = self.camera.project_3d_to_2d((connector.start_pos.x, connector.start_pos.y, connector.start_pos.z))
        end_2d = self.camera.project_3d_to_2d((connector.end_pos.x, connector.end_pos.y, connector.end_pos.z))
        
        if start_2d and end_2d:
            # Color verde para conectores subterráneos
            color = (0, 200, 100) if connector.start_pos.z < -5 else (100, 200, 100)
            pygame.draw.line(self.screen, color, start_2d, end_2d, 3)
            
    def draw_boarding_lane(self, lane):
        """Dibuja un BoardingLane con un color distintivo."""
        start_2d = self.camera.project_3d_to_2d((lane.start_pos.x, lane.start_pos.y, lane.start_pos.z))
        end_2d = self.camera.project_3d_to_2d((lane.end_pos.x, lane.end_pos.y, lane.end_pos.z))
        
        if start_2d and end_2d:
            # Color cian brillante para los andenes de embarque
            color = (0, 255, 255)
            pygame.draw.line(self.screen, color, start_2d, end_2d, 4) # Línea un poco más gruesa

    def draw_acceleration_tree(self, tree):
        """Dibuja un árbol de aceleración con colores según la dirección"""
        # Calcular puntos a lo largo del árbol para una línea suave
        points = []
        num_segments = 20
        
        for i in range(num_segments + 1):
            progress = i / num_segments
            point_3d = tree.calculate_position_at_progress(progress)
            point_2d = self.camera.project_3d_to_2d((point_3d.x, point_3d.y, point_3d.z))
            if point_2d:
                points.append(point_2d)
        
    def draw_acceleration_tree(self, tree):
        """Dibuja un árbol de aceleración con colores según la dirección"""
        # Calcular puntos a lo largo del árbol para una línea suave
        points = []
        num_segments = 20
        
        for i in range(num_segments + 1):
            progress = i / num_segments
            point_3d = tree.calculate_position_at_progress(progress)
            point_2d = self.camera.project_3d_to_2d((point_3d.x, point_3d.y, point_3d.z))
            if point_2d:
                points.append(point_2d)
        
        # Dibujar línea con color según la dirección
        if len(points) > 1:
            if tree.direction == "down":
                color = (255, 100, 100)  # Rojo para bajada (aceleración)
            else:  # "up"
                color = (100, 100, 255)  # Azul para subida (desaceleración)
            
            pygame.draw.lines(self.screen, color, False, points, 3)
            
            # Dibujar punto al inicio y final
            if points:
                pygame.draw.circle(self.screen, color, points[0], 4)
                pygame.draw.circle(self.screen, color, points[-1], 4)
      
    def draw_station(self, station):
        """Dibuja una estación como prismas rectangulares de 3 pisos creciendo hacia arriba"""
        # NUEVAS DIMENSIONES según especificaciones
        width = 50      # metros en eje X (ancho)
        length = 60     # metros en eje Y (largo)
        floor_height = 4.9  # metros de alto por piso
        floor_spacing = 1.0 # metros entre pisos

        # Posición de la estación - el punto de origen está en la BASE
        center_x, center_y, base_z = station.position.x, station.position.y, station.position.z

        # Dibujar cada uno de los 3 pisos, desde el más bajo (naranja) hasta el más alto (rojo)
        for floor_level in range(3):
            # Calcular la altura de la base de cada piso
            # El piso 0 (naranja) está en la base, luego sube floor_spacing + floor_height para cada piso siguiente
            floor_base_z = base_z + (floor_height + floor_spacing) * floor_level
            
            half_width = width / 2
            half_length = length / 2

            # Vertices del prisma para este piso
            vertices = [
                # Cara superior del piso
                (center_x - half_width, center_y - half_length, floor_base_z + floor_height),
                (center_x + half_width, center_y - half_length, floor_base_z + floor_height),
                (center_x + half_width, center_y + half_length, floor_base_z + floor_height),
                (center_x - half_width, center_y + half_length, floor_base_z + floor_height),
                
                # Cara inferior del piso
                (center_x - half_width, center_y - half_length, floor_base_z),
                (center_x + half_width, center_y - half_length, floor_base_z),
                (center_x + half_width, center_y + half_length, floor_base_z),
                (center_x - half_width, center_y + half_length, floor_base_z)
            ]
            
            # Proyectar vértices a 2D
            vertices_2d = []
            for v in vertices:
                projected = self.camera.project_3d_to_2d(v)
                if projected:
                    vertices_2d.append(projected)
            
            # Color diferente para cada piso (según el orden especificado)
            floor_colors = [
                (255, 150, 100),   # Piso 0 - naranja (base, donde se toman los VMs)
                (150, 150, 200),   # Piso 1 - azul/morado (pago de tiquetes)
                (255, 100, 100)    # Piso 2 - rojo (el más alto)
            ]
            
            # Dibujar las caras del prisma si tenemos suficientes puntos proyectados
            if len(vertices_2d) >= 8:
                color = floor_colors[floor_level]
                
                # Cara superior
                pygame.draw.polygon(self.screen, color, 
                                [vertices_2d[0], vertices_2d[1], vertices_2d[2], vertices_2d[3]], 1)
                
                # Cara inferior
                pygame.draw.polygon(self.screen, color, 
                                [vertices_2d[4], vertices_2d[5], vertices_2d[6], vertices_2d[7]], 1)
                
                # Caras laterales
                for i in range(4):
                    # Conectar cara superior e inferior
                    pygame.draw.line(self.screen, color, vertices_2d[i], vertices_2d[i+4], 1)
                    # Bordes de la cara superior
                    next_i = (i + 1) % 4
                    pygame.draw.line(self.screen, color, vertices_2d[i], vertices_2d[next_i], 1)
                    # Bordes de la cara inferior
                    pygame.draw.line(self.screen, color, vertices_2d[i+4], vertices_2d[next_i+4], 1)
        
    def draw_vehicle(self, vehicle):
        """Dibuja un vehículo modular con dimensiones 1m (largo) × 1m (ancho) × 1.5m (alto)"""
        # NUEVAS DIMENSIONES según especificaciones
        length = 1.0    # 1 metro de largo (eje X)
        width = 1.0     # 1 metro de ancho (eje Y) 
        height = 1.5    # 1.5 metros de alto (eje Z)
        
        half_length = length / 2
        half_width = width / 2
        half_height = height / 2

        # Usar la posición actual del vehículo (centro de la base)
        pos = vehicle.current_position
        
        # Definir los 8 vértices del prisma rectangular
        vertices = [
            # Cara inferior (base)
            (pos.x - half_length, pos.y - half_width, pos.z),           # 0: esquina inferior-izquierda-atrás
            (pos.x + half_length, pos.y - half_width, pos.z),           # 1: esquina inferior-derecha-atrás  
            (pos.x + half_length, pos.y + half_width, pos.z),           # 2: esquina inferior-derecha-delante
            (pos.x - half_length, pos.y + half_width, pos.z),           # 3: esquina inferior-izquierda-delante
            
            # Cara superior (techo)
            (pos.x - half_length, pos.y - half_width, pos.z + height),  # 4: esquina superior-izquierda-atrás
            (pos.x + half_length, pos.y - half_width, pos.z + height),  # 5: esquina superior-derecha-atrás
            (pos.x + half_length, pos.y + half_width, pos.z + height),  # 6: esquina superior-derecha-delante
            (pos.x - half_length, pos.y + half_width, pos.z + height)   # 7: esquina superior-izquierda-delante
        ]
        
        # Proyectar vértices a 2D
        vertices_2d = []
        for v in vertices:
            projected = self.camera.project_3d_to_2d(v)
            if projected:
                vertices_2d.append(projected)
        
        # Dibujar el prisma si tenemos suficientes puntos
        if len(vertices_2d) >= 8:
            # Color según el estado del vehículo
            if vehicle.is_colliding:
                color = (255, 0, 255) # Magenta brillante para colisión
            elif vehicle.current_station and not vehicle.current_track:
                color = (255, 200, 0)  # Amarillo para "pasando por estación"
            elif vehicle.state in ["accelerating_down", "accelerating_up"]:
                color = (255, 100, 100)  # Rojo para aceleración
            elif vehicle.state == "moving":
                color = (100, 255, 100)  # Verde para movimiento constante
            else:
                color = (255, 255, 255)  # Blanco para otros estados
            
            # Definir las caras del prisma
            faces = [
                # Cara frontal (delante)
                [vertices_2d[3], vertices_2d[2], vertices_2d[6], vertices_2d[7]],
                # Cara trasera (atrás)
                [vertices_2d[0], vertices_2d[1], vertices_2d[5], vertices_2d[4]],
                # Cara izquierda
                [vertices_2d[0], vertices_2d[3], vertices_2d[7], vertices_2d[4]],
                # Cara derecha
                [vertices_2d[1], vertices_2d[2], vertices_2d[6], vertices_2d[5]],
                # Cara superior (techo)
                [vertices_2d[4], vertices_2d[5], vertices_2d[6], vertices_2d[7]],
                # Cara inferior (base)
                [vertices_2d[0], vertices_2d[1], vertices_2d[2], vertices_2d[3]]
            ]
            
            # Dibujar cada cara
            for face in faces:
                if len(face) == 4:
                    pygame.draw.polygon(self.screen, color, face, 1)
            
            # Resaltar aristas principales para mejor visibilidad
            edge_pairs = [
                # Aristas verticales
                (vertices_2d[0], vertices_2d[4]), (vertices_2d[1], vertices_2d[5]),
                (vertices_2d[2], vertices_2d[6]), (vertices_2d[3], vertices_2d[7]),
                # Aristas del techo
                (vertices_2d[4], vertices_2d[5]), (vertices_2d[5], vertices_2d[6]),
                (vertices_2d[6], vertices_2d[7]), (vertices_2d[7], vertices_2d[4]),
                # Aristas de la base
                (vertices_2d[0], vertices_2d[1]), (vertices_2d[1], vertices_2d[2]),
                (vertices_2d[2], vertices_2d[3]), (vertices_2d[3], vertices_2d[0])
            ]
            
            for start, end in edge_pairs:
                pygame.draw.line(self.screen, color, start, end, 2)

    def draw_debug_info(self, simulation):
        """Muestra información de depuración"""
        font = pygame.font.SysFont('Arial', 12)
        used_positions = []
        
        # Mostrar información de estaciones
        for station in simulation.stations:
            station_info = f"S{station.station_id}: {station.name}"
            pos_2d = self.camera.project_3d_to_2d((
                station.position.x, 
                station.position.y + 20, 
                station.position.z
            ))
            
            if pos_2d and self._is_position_available(pos_2d, used_positions, font.size(station_info)):
                text = font.render(station_info, True, (0, 255, 0))
                self.screen.blit(text, pos_2d)
                used_positions.append((pos_2d[0], pos_2d[1], text.get_width(), text.get_height()))
        
        # Mostrar información de vehículos
        for vehicle in simulation.vehicles:
            # Color de velocidad
            speed = vehicle.velocity.length()
            if speed > 15:
                speed_color = (255, 0, 0)
            elif speed > 10:
                speed_color = (255, 165, 0)
            elif speed > 5:
                speed_color = (255, 255, 0)
            else:
                speed_color = (200, 200, 200)
            
            # Información en una sola línea para mayor claridad
            state_short = vehicle.state[:4] # "movi", "acce", etc.
            track_info = f"T:{vehicle.current_track.track_id}" if vehicle.current_track else "NoTrack"
            dest_info = f"->S{vehicle.destination_station}" if vehicle.destination_station else ""

            # ✅ MEJORA: Mensaje de colisión más informativo y conciso
            if vehicle.is_colliding:
                # Extraer solo los números de los IDs para un mensaje más corto
                colliding_ids = [vid.split('_')[-1] for vid in vehicle.colliding_with]
                collision_alert = f"!!COL with {','.join(colliding_ids)}!!"
            else:
                collision_alert = ""
            info_line = f"VM{vehicle.vehicle_id} [{state_short}|{track_info}] V:{speed:.1f} {dest_info} {collision_alert}".strip()

            pos_2d = self.camera.project_3d_to_2d((
                vehicle.current_position.x, 
                vehicle.current_position.y + 8, 
                vehicle.current_position.z
            ))

            if vehicle.is_colliding:
                text_color = (255, 0, 255) # Magenta
            elif vehicle.destination_station:
                text_color = (180, 255, 180) # Verde claro si tiene destino
            else:
                text_color = (200, 200, 200) # Blanco si no

            if pos_2d and self._is_position_available(pos_2d, used_positions, font.size(info_line)):
                text = font.render(info_line, True, text_color)
                self.screen.blit(text, pos_2d)
                used_positions.append((pos_2d[0], pos_2d[1], text.get_width(), text.get_height()))
        
        # Mostrar información de tracks
        for track_id, track in simulation.network.tracks.items():
            if hasattr(track, 'get_track_type'):
                mid_point = track.calculate_position_at_progress(0.5)
                track_info = f"T:{track_id}"
                pos_2d = self.camera.project_3d_to_2d((
                        mid_point.x, 
                        mid_point.y + 5, 
                        mid_point.z
                    ))
                
                if pos_2d:
                    color = (180, 180, 255) if hasattr(track, 'direction') and track.direction == "up" else (255, 180, 180)
                    text = font.render(track_info, True, color)
                    if self._is_position_available(pos_2d, used_positions, text.get_size()):
                        self.screen.blit(text, pos_2d)
                        used_positions.append((pos_2d[0], pos_2d[1], text.get_width(), text.get_height()))

    def _is_position_available(self, pos_2d, used_positions, text_size, margin=2):
        """Verifica si una posición está disponible para dibujar texto sin superponerse"""
        x, y = pos_2d
        w, h = text_size
        new_rect = (x - margin, y - margin, w + 2*margin, h + 2*margin)
        
        for used in used_positions:
            if (new_rect[0] < used[0] + used[2] and
                new_rect[0] + new_rect[2] > used[0] and
                new_rect[1] < used[1] + used[3] and
                new_rect[1] + new_rect[3] > used[1]):
                return False
        return True