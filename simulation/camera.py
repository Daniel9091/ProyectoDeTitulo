import pygame                                                                               # Librería para manejo de gráficos y eventos
import math                                                                                 # Librería matemática para cálculos trigonométricos

class Camera:                                                                               # Clase para manejar la cámara en vista isométrica        
    def __init__(self, width, height):                                                      # Configuración inicial de la cámara 
        # Posición y orientación inicial de la cámara
        self.x = 0
        self.y = 0
        self.z = 0

        self.zoom = 0.8                                                                     # Zoom inicial más cercano

        self.theta = 0                                                                      # Ángulo horizontal inicial (sin límite)
        self.alpha = 0                                                                      # Angulo vertical inicial (sin límite)

        self.screen_width = width                                                           # Ancho de la pantalla (definido externamente)[main]
        self.screen_height = height                                                         # Alto de la pantalla  (definido externamente)[main]
        
        # coniguración de velocidades de movimiento
        self.move_speed = 200.0                                                             # Velocidad de movimiento horizontal 
        self.vertical_move_speed = 200.0                                                    # Velocidad de movimiento vertical
        self.rotation_speed = 180.0                                                         # Velocidad de rotación (grados por segundo)
        self.zoom_speed = 0.2                                                               # Velocidad de zoom (factor multiplicativo)
        
    def handle_event(self, event):                                                          # Procesa eventos del teclado y raton y retorna acciones especificas que despues aplica el main
        if event.type == pygame.KEYDOWN:                                                    # Controles del teclado
            # controles para el tiempo de la simlacion
            if event.key == pygame.K_PLUS:                                                  # +     
                return "time_scale_up"
            elif event.key == pygame.K_MINUS:                                               # -     
                return "time_scale_down"
            # control para resetear la simulacion
            elif event.key == pygame.K_0:                                                   # 0                                            
                return "reset_simulation"
            # control para rebobinar temporalmente
            elif event.key == pygame.K_BACKSPACE:                                           #  backspace (flecha para borrar)
                return "rewind_temporary"
            # control para pausar/reanudar la simulacion
            elif event.key == pygame.K_p:                                                   # P
                return "time_pause"
            # Controles para velocidad de movimiento horizontal
            elif event.key == pygame.K_1:                                                   # 1 (aumentar)
                return "increase_move_speed"
            elif event.key == pygame.K_2:
                return "decrease_move_speed"                                                # 2 (disminuir)
            # Controles para velocidad de movimiento vertical
            elif event.key == pygame.K_3:
                return "increase_vertical_speed"                                            # 3 (aumentar)
            elif event.key == pygame.K_4:
                return "decrease_vertical_speed"                                            # 4 (disminuir)
            # Controles para velocidad de rotación
            elif event.key == pygame.K_5:
                return "increase_rotation_speed"                                            # 5 (aumentar)
            elif event.key == pygame.K_6:
                return "decrease_rotation_speed"                                            # 6 (disminuir)
            # Controles para velocidad de zoom
            elif event.key == pygame.K_7:
                return "increase_zoom_speed"                                                # 7 (aumentar)  
            elif event.key == pygame.K_8:
                return "decrease_zoom_speed"                                               # 8 (disminuir)
                
        elif event.type == pygame.MOUSEBUTTONDOWN:                                          # Controles para zoom con rueda del ratón
            if event.button == 4:                                                           # Rueda arriba
                self.zoom_in()
            elif event.button == 5:                                                         # Rueda abajo
                self.zoom_out()
                
        return None                                                                         # Si no se detecta ninguna acción relevante, retorna None
    
    def update(self, keys, dt):                                                             # Acutaliza posición y orientación de la cámara en base a las teclas presionadas
        # caluclo de las distancias de movimiento y rotación según el tiempo delta
        move_amount = self.move_speed * dt
        vertical_move_amount = self.vertical_move_speed * dt
        rotate_amount = self.rotation_speed * dt
        
        # Movimiento horizontal (WASD)
        if keys[pygame.K_a]:                                                                # A (movimiento izquierda)
            self.x -= move_amount
        if keys[pygame.K_d]:                                                                # D (movimiento derecha)
            self.x += move_amount
        if keys[pygame.K_w]:                                                                # W (movimiento arriba)
            self.y -= move_amount
        if keys[pygame.K_s]:                                                                # S (movimiento abajo)                                                      
            self.y += move_amount
            
        # Movimiento vertical (QE)
        if keys[pygame.K_q]:                                                                # Q (movimiento abajo)
            self.z -= vertical_move_amount
        if keys[pygame.K_e]:                                                                # E (movimiento arriba)
            self.z += vertical_move_amount
            
        # Zoom con teclas (ZX)
        if keys[pygame.K_z]:                                                                # Z (zoom in)
            self.zoom_in()
        if keys[pygame.K_x]:                                                                # X (zoom out)
            self.zoom_out()
            
        # Rotación (flechas) - sin limites
        # En torno al eje z (izquierda/derecha)
        if keys[pygame.K_LEFT]:
            self.theta -= rotate_amount
        if keys[pygame.K_RIGHT]:
            self.theta += rotate_amount
        # En torno al eje x (arriba/abajo)
        if keys[pygame.K_UP]:
            self.alpha -= rotate_amount 
        if keys[pygame.K_DOWN]:
            self.alpha += rotate_amount

        self.normalize_angle()                                                              # Mantiene los angulos entre 0 y 360 grados    

    def normalize_angle(self):                                                              # Mantine los angulos entre 0 y 360 grados
        self.theta %= 360
        self.alpha %= 360

    def zoom_in(self):                                                                      # Acerca la camara
        self.zoom *= (1 + self.zoom_speed)
        
    def zoom_out(self):                                                                     # Aleja la camara
        self.zoom /= (1 + self.zoom_speed)
    
    def get_info(self):                                                                     # Retorna informacion de la camara para mostrar en UI
        return {
            'position': (self.x, self.y, self.z),
            'rotation': (self.theta, self.alpha),
            'zoom': self.zoom,
            'move_speed': self.move_speed,
            'vertical_speed': self.vertical_move_speed,
            'rotation_speed': self.rotation_speed,
            'zoom_speed': self.zoom_speed
        }
    
    def project_3d_to_2d(self, point_3d):                                                   # Projecta un punto 3D a coordenadas 2D de pantalla 
        x, y, z = point_3d
        
        # Aplicar rotaciones
        theta_rad = math.radians(self.theta)
        alpha_rad = math.radians(self.alpha)
        
        # Primero: trasladar el punto según la posición de la cámara
        x_rel = x - self.x
        y_rel = y - self.y
        z_rel = z - self.z
        
        # Rotación horizontal (theta) - alrededor del eje Y
        x_rot = x_rel * math.cos(theta_rad) + z_rel * math.sin(theta_rad)
        z_rot = -x_rel * math.sin(theta_rad) + z_rel * math.cos(theta_rad)
        
        # Rotación vertical (alpha) - alrededor del eje X
        y_rot = y_rel * math.cos(alpha_rad) - z_rot * math.sin(alpha_rad)
        z_final = y_rel * math.sin(alpha_rad) + z_rot * math.cos(alpha_rad)
        
        # Aplicar zoom y centrar en pantalla
        x_screen = (x_rot * self.zoom) + self.screen_width / 2
        y_screen = (z_final * self.zoom) + self.screen_height / 2
        
        return (int(x_screen), int(y_screen))                                               # Retorna las coordenadas 2D en pantalla