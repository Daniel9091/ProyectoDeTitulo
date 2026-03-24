import pygame
from ui.info_panel import draw_info_panel
import math
from objects.base import Vector3
from objects.passenger import Passenger 



class Renderer:
    # ─────────────────────────────────────────────────────────────────
    # CULL_MARGIN: margen de culling para vehículos y pasajeros.
    #
    #   = 0   → se dibuja exactamente lo que cabe en la ventana (normal)
    #   > 0   → se dibuja un poco más allá del borde (por si algo se corta)
    #   < 0   → se dibuja MENOS que la los vms que pasan por el cariril inferior para que se muevan de amnera discreta y afiliados a una cola vale decir que todos los vms esten relacionados con un puto en el carril que se va a ir movieno en el tiempo de tal manera que cuando uno quiera saber la posicion de un vm  pregunte deonde esta la cola y despues pueda sumar sierta distancia a la cola y encontrarse con un espacio deonde degeria o no haber un vm. ventana completa (útil para demos:
    #            verás un rectángulo amarillo que indica el área activa y
    #            los VMs fuera de él desaparecerán)
    #
    # Ejemplo para el experimento: cambia a -200 y verás el efecto visual.
    # Para producción déjalo en 0.
    # ─────────────────────────────────────────────────────────────────
    CULL_MARGIN = 0

    def __init__(self, screen, camera):
        self.screen = screen
        self.camera = camera
        # Cache de fuentes para evitar SysFont() en cada frame
        self._font_debug = pygame.font.SysFont('Arial', 12)
        self._font_label = pygame.font.SysFont('Arial', 14, bold=True)
        # Estadísticas de rendering (actualizadas cada frame)
        self._vehicles_drawn = 0
        self._vehicles_total = 0

    def draw(self, simulation):
        self.screen.fill((20, 20, 30))

        # Tracks: siempre se dibujan (son ~20 y estáticos, costo mínimo)
        self.draw_network_tracks(simulation.network)

        # Estaciones
        for station in simulation.stations:
            self.draw_station(station)

        # Vehículos — con culling
        self._vehicles_total = len(simulation.vehicles)
        self._vehicles_drawn = 0
        for vehicle in simulation.vehicles:
            self.draw_vehicle(vehicle, simulation)

        # Pasajeros — con culling
        for passenger in simulation.passengers.values():
            self.draw_passenger(passenger)

        self.draw_debug_points(simulation)
        self.draw_debug_info(simulation)

        # Rectángulo amarillo que muestra el área de culling (solo cuando CULL_MARGIN < 0)
        if self.CULL_MARGIN < 0:
            self._draw_cull_boundary()

        if simulation.show_info:
            draw_info_panel(self.screen, simulation, self.camera)

    def _draw_cull_boundary(self):
        """Dibuja un rectángulo amarillo mostrando el área activa de culling."""
        m = -self.CULL_MARGIN  # positivo: cuántos px se recorta por cada borde
        w = self.camera.screen_width
        h = self.camera.screen_height
        rect = pygame.Rect(m, m, w - 2 * m, h - 2 * m)
        pygame.draw.rect(self.screen, (255, 220, 0), rect, 2)
        label = self._font_label.render(
            f"ZONA DE CULLING  (CULL_MARGIN={self.CULL_MARGIN})", True, (255, 220, 0))
        self.screen.blit(label, (m + 4, m + 4))

    def draw_debug_points(self, simulation):
        """Dibuja puntos de depuración específicos en el mundo."""
        if not hasattr(simulation, 'debug_points'):
            return

        for point_data in simulation.debug_points:
            pos_3d = point_data['pos']
            color = point_data.get('color', (255, 100, 0))
            label = point_data.get('label', '')

            # Culling: solo dibujar si el punto está en pantalla
            pos_2d = self.camera.project_3d_to_2d((pos_3d.x, pos_3d.y, pos_3d.z), margin=0)

            if pos_2d:
                world_radius = point_data.get('radius', 1.0)
                pixel_radius = int(world_radius * self.camera.zoom)
                pygame.draw.circle(self.screen, color, pos_2d, max(2, pixel_radius), 2)
                if label:
                    text = self._font_label.render(label, True, color)
                    self.screen.blit(text, (pos_2d[0] + 10, pos_2d[1] - 10))
    
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
        """Dibuja un StationConnector como una línea recta.
        Sin culling: hay ~20 tracks y son estáticos; el costo es despreciable
        comparado con no verlos cuando cruzan el borde de la pantalla."""
        start_2d = self.camera.project_3d_to_2d(
            (connector.start_pos.x, connector.start_pos.y, connector.start_pos.z))
        end_2d = self.camera.project_3d_to_2d(
            (connector.end_pos.x, connector.end_pos.y, connector.end_pos.z))
        color = (0, 200, 100) if connector.start_pos.z < -5 else (100, 200, 100)
        pygame.draw.line(self.screen, color, start_2d, end_2d, 3)

    def draw_boarding_lane(self, lane):
        """Dibuja un BoardingLane con un color distintivo."""
        start_2d = self.camera.project_3d_to_2d(
            (lane.start_pos.x, lane.start_pos.y, lane.start_pos.z))
        end_2d = self.camera.project_3d_to_2d(
            (lane.end_pos.x, lane.end_pos.y, lane.end_pos.z))
        pygame.draw.line(self.screen, (0, 255, 255), start_2d, end_2d, 4)

    def draw_acceleration_tree(self, tree):
        """Dibuja un árbol de aceleración con colores según la dirección.
        Sin culling: hay pocos árboles y pueden cruzar el borde de cualquier forma."""
        points = []
        num_segments = 20
        for i in range(num_segments + 1):
            progress = i / num_segments
            point_3d = tree.calculate_position_at_progress(progress)
            points.append(self.camera.project_3d_to_2d((point_3d.x, point_3d.y, point_3d.z)))

        if len(points) > 1:
            color = (255, 100, 100) if tree.direction == "down" else (100, 100, 255)
            pygame.draw.lines(self.screen, color, False, points, 3)
            pygame.draw.circle(self.screen, color, points[0], 4)
            pygame.draw.circle(self.screen, color, points[-1], 4)
      
    def draw_station(self, station):
        """Dibuja una estación como prismas rectangulares de 3 pisos creciendo hacia arriba"""
        width = 50      # metros en eje X (ancho)
        length = 60     # metros en eje Y (largo)
        floor_height = 4.9  # metros de alto por piso
        floor_spacing = 1.0 # metros entre pisos

        center_x, center_y, base_z = station.position.x, station.position.y, station.position.z

        # Culling: margen generoso (300px) por el tamaño de la estación en pantalla
        center_2d = self.camera.project_3d_to_2d((center_x, center_y, base_z), margin=300)
        if not center_2d:
            return

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
        
    def draw_vehicle(self, vehicle, simulation):
        """Dibuja un vehículo modular con dimensiones 1m (largo) × 1m (ancho) × 1.5m (alto)"""
        length = 1.0
        width = 1.0
        height = 1.5

        half_length = length / 2
        half_width = width / 2

        pos = vehicle.current_position

        # Culling: saltar si el centro del vehículo está fuera del área activa
        center_2d = self.camera.project_3d_to_2d((pos.x, pos.y, pos.z), margin=self.CULL_MARGIN)
        if not center_2d:
            return
        self._vehicles_drawn += 1
        
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

                # # --- NUEVO: LOGGING DE DIAGNÓSTICO DE COLISIÓN ---
                # # Solo registrar la colisión una vez por cada par de vehículos
                # collision_pair = tuple(sorted((vehicle.vehicle_id, *vehicle.colliding_with)))
                # if collision_pair not in simulation.logged_collisions:
                #     simulation.logged_collisions.add(collision_pair)
                    
                #     print("\n" + "="*30 + " 💥 COLISIÓN DETECTADA 💥 " + "="*30)
                #     print(f"Tiempo de Simulación: {simulation.brain.simulation_time:.3f}s")
                    
                #     # Obtener las instancias de los vehículos que chocan
                #     colliding_vehicles = [v for v in simulation.vehicles if v.vehicle_id in collision_pair]

                #     for v in colliding_vehicles:
                #         track_id = v.current_track.track_id if v.current_track else "N/A"
                #         track_type = v.current_track.get_track_type() if v.current_track else "N/A"
                #         progress = v.current_track.get_vehicle_progress(v) if v.current_track else -1.0
                        
                #         print(f"\n--- Vehículo Implicado: {v.vehicle_id} ---")
                #         print(f"  - Estado: {v.state}")
                #         print(f"  - Track Actual: ID {track_id} (Tipo: {track_type})")
                #         print(f"  - Progreso en Track: {progress:.4f}")
                #         print(f"  - Velocidad: {v.velocity.length():.2f} m/s")
                #         print(f"  - Posición: {v.current_position}")
                #     print("="*80 + "\n")
                # # --- FIN LOGGING ---

            elif vehicle.current_station and not vehicle.current_track and not getattr(vehicle, '_in_train', False):
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
        font = self._font_debug  # reusar font cacheado
        used_positions = []

        # ── Contador de culling: VMs dibujados vs total ──────────────
        cull_text = f"VMs dibujados: {self._vehicles_drawn} / {self._vehicles_total}  (CULL_MARGIN={self.CULL_MARGIN})"
        cull_surf = font.render(cull_text, True, (255, 220, 0))
        self.screen.blit(cull_surf, (8, self.camera.screen_height - 20))

        # Mostrar información de estaciones
        for station in simulation.stations:
            station_info = f"S{station.station_id}: {station.name}"
            pos_2d = self.camera.project_3d_to_2d((
                station.position.x,
                station.position.y + 20,
                station.position.z
            ), margin=0)
            
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
            if vehicle.current_track:
                track_info = f"T:{vehicle.current_track.track_id}"
            elif getattr(vehicle, '_in_train', False):
                track_info = f"S:{getattr(vehicle, '_train_slot', '?')}"
            else:
                track_info = "NoTrack"
            dest_info = f"->S{vehicle.destination_station}" if vehicle.destination_station else ""

            # ✅ MEJORA: Mensaje de colisión más informativo y conciso
            if vehicle.is_colliding:
                # Extraer solo los números de los IDs para un mensaje más corto
                colliding_ids = [vid.split('_')[-1] for vid in vehicle.colliding_with]
                collision_alert = f"!!COL with {','.join(colliding_ids)}!!"
            else:
                collision_alert = ""
            coord_x_info = f"X:{vehicle.current_position.x:.1f}"
            info_line = f"VM{vehicle.vehicle_id} [{state_short}|{track_info}] V:{speed:.1f} {coord_x_info} {dest_info} {collision_alert}".strip()

            pos_2d = self.camera.project_3d_to_2d((
                vehicle.current_position.x,
                vehicle.current_position.y + 8,
                vehicle.current_position.z
            ), margin=0)

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
        
        # --- NUEVO BUCLE PARA PASAJEROS ---
        for passenger in simulation.passengers.values():
            if passenger.state == 'IN_TRANSIT' or passenger.state == 'ARRIVED':
                continue # No dibujar info si está en un VM o ya llegó

            # Información del pasajero
            state_short = passenger.state[:7] # "WAITING", "MOVING_", "BOARDIN"
            dest_info = f"->S{passenger.destination_station_id}"
            pass_id_short = passenger.passenger_id.split('_')[-1][:4] # "P_abc1"
            
            info_line = f"P:{pass_id_short} [{state_short}] {dest_info}"
            
            # Posición (ligeramente por encima del pasajero)
            pos_3d = passenger.current_position
            pos_2d = self.camera.project_3d_to_2d((
                pos_3d.x,
                pos_3d.y,
                pos_3d.z + 1.0
            ), margin=0)

            if passenger.state == 'BOARDING':
                text_color = (0, 255, 255) # Cian
            else:
                text_color = (255, 255, 200) # Amarillo claro

            if pos_2d and self._is_position_available(pos_2d, used_positions, font.size(info_line)):
                text = font.render(info_line, True, text_color)
                self.screen.blit(text, pos_2d)
                used_positions.append((pos_2d[0], pos_2d[1], text.get_width(), text.get_height()))
        # --- FIN NUEVO BUCLE PARA PASAJEROS ---
        
        # Mostrar información de tracks
        for track_id, track in simulation.network.tracks.items():
            if hasattr(track, 'get_track_type'):
                mid_point = track.calculate_position_at_progress(0.5)
                track_info = f"T:{track_id}"
                pos_2d = self.camera.project_3d_to_2d((
                    mid_point.x,
                    mid_point.y + 5,
                    mid_point.z
                ), margin=0)
                
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

    def draw_passenger(self, passenger: 'Passenger'):
        """Dibuja un pasajero en su posición actual."""
        # 1. No dibujar si está dentro de un vehículo o ya llegó
        if passenger.state == 'IN_TRANSIT' or passenger.state == 'ARRIVED':
            return
            
        # 2. Proyectar posición 3D a 2D — saltar si fuera del área activa
        pos_3d = passenger.current_position
        pos_2d = self.camera.project_3d_to_2d((pos_3d.x, pos_3d.y, pos_3d.z), margin=self.CULL_MARGIN)
        
        if pos_2d:
            # 3. Elegir color según el estado
            if passenger.state == 'BOARDING':
                color = (0, 255, 255) # Cian (para ver la sincronización)
            elif passenger.state == 'WAITING_IN_LANE_QUEUE':
                color = (255, 0, 0)   # Rojo (esperando en andén)
            elif passenger.state == 'MOVING_TO_LANE':
                color = (255, 165, 0) # Naranja (caminando)
            else:
                color = (255, 255, 0) # Amarillo (default)
            
            # 4. Dibujar el círculo (radio de 3 píxeles)
            pygame.draw.circle(self.screen, color, pos_2d, 3)