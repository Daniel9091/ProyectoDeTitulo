import pygame
import math

class Camera:
    def __init__(self, width, height):
        self.screen_width = width
        self.screen_height = height
        self.reset()  # Inicializar todos los valores llamando a reset()
    
    def reset(self):
        """Resetea la cámara a su posición y rotación inicial"""
        self.x = 0  # Posición centrada en X
        self.y = 0  # Posición centrada en Y  
        self.z = 0    # Altura base
        self.zoom = 0.8
        self.theta = 0
        self.alpha = 90  # Vista desde arriba
        
        # Velocidades por defecto
        self.move_speed = 200.0
        self.vertical_move_speed = 200.0
        self.rotation_speed = 180.0
        self.zoom_speed = 0.2
        
        print("Cámara resetada - Posición:", (self.x, self.y, self.z), "Rotación:", (self.theta, self.alpha))
    
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            # Controles para el tiempo de la simulación
            if event.key == pygame.K_PLUS:
                return "time_scale_up"
            elif event.key == pygame.K_MINUS:
                return "time_scale_down"
            elif event.key == pygame.K_0:
                return "reset_simulation"
            elif event.key == pygame.K_BACKSPACE:
                return "rewind_temporary"
            elif event.key == pygame.K_p:
                return "time_pause"
            # Controles para velocidades
            elif event.key == pygame.K_1:
                return "increase_move_speed"
            elif event.key == pygame.K_2:
                return "decrease_move_speed"
            elif event.key == pygame.K_3:
                return "increase_vertical_speed"
            elif event.key == pygame.K_4:
                return "decrease_vertical_speed"
            elif event.key == pygame.K_5:
                return "increase_rotation_speed"
            elif event.key == pygame.K_6:
                return "decrease_rotation_speed"
            elif event.key == pygame.K_7:
                return "increase_zoom_speed"
            elif event.key == pygame.K_8:
                return "decrease_zoom_speed"
                
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:  # Rueda arriba
                self.zoom_in()
            elif event.button == 5:  # Rueda abajo
                self.zoom_out()
                
        return None
    
    def update(self, keys, dt):
        move_amount = self.move_speed * dt
        vertical_move_amount = self.vertical_move_speed * dt
        rotate_amount = self.rotation_speed * dt
        
        # MOVIMIENTO HORIZONTAL CORREGIDO
        if keys[pygame.K_a]:  # A (movimiento IZQUIERDA - Oeste)
            self.x -= move_amount
        if keys[pygame.K_d]:  # D (movimiento DERECHA - Este)
            self.x += move_amount
        if keys[pygame.K_w]:  # W (movimiento NORTE - aumentar Y)
            self.y += move_amount
        if keys[pygame.K_s]:  # S (movimiento SUR - disminuir Y)
            self.y -= move_amount
            
        # MOVIMIENTO VERTICAL  
        if keys[pygame.K_q]:  # Q (movimiento ABAJO)
            self.z -= vertical_move_amount
        if keys[pygame.K_e]:  # E (movimiento ARRIBA)
            self.z += vertical_move_amount
            
        # ZOOM
        if keys[pygame.K_z]:
            self.zoom_in()
        if keys[pygame.K_x]:
            self.zoom_out()
            
        # ROTACIÓN
        if keys[pygame.K_LEFT]:
            self.theta -= rotate_amount
        if keys[pygame.K_RIGHT]:
            self.theta += rotate_amount
        if keys[pygame.K_UP]:
            self.alpha -= rotate_amount 
        if keys[pygame.K_DOWN]:
            self.alpha += rotate_amount

        self.normalize_angle()
    
    def normalize_angle(self):
        self.theta %= 360
        self.alpha %= 360

    def zoom_in(self):
        self.zoom *= (1 + self.zoom_speed)
        
    def zoom_out(self):
        self.zoom /= (1 + self.zoom_speed)
    
    def get_info(self):
        return {
            'position': (self.x, self.y, self.z),
            'rotation': (self.theta, self.alpha),
            'zoom': self.zoom,
            'move_speed': self.move_speed,
            'vertical_speed': self.vertical_move_speed,
            'rotation_speed': self.rotation_speed,
            'zoom_speed': self.zoom_speed
        }
    
    def project_3d_to_2d(self, point_3d):
        x, y, z = point_3d
        
        # Aplicar rotaciones
        theta_rad = math.radians(self.theta)
        alpha_rad = math.radians(self.alpha)
        
        # Primero: trasladar el punto según la posición de la cámara
        x_rel = x - self.x
        y_rel = y - self.y
        z_rel = z - self.z
        
        # Rotación horizontal (theta) - alrededor del eje Z
        x_rot = x_rel * math.cos(theta_rad) - y_rel * math.sin(theta_rad)
        y_rot = x_rel * math.sin(theta_rad) + y_rel * math.cos(theta_rad)
        z_rot = z_rel  # Z no se afecta por rotación horizontal
        
        # Rotación vertical (alpha) - alrededor del eje X
        y_final = y_rot * math.cos(alpha_rad) - z_rot * math.sin(alpha_rad)
        z_final = y_rot * math.sin(alpha_rad) + z_rot * math.cos(alpha_rad)
        
        # Aplicar zoom y centrar en pantalla
        x_screen = (x_rot * self.zoom) + self.screen_width / 2
        y_screen = (y_final * self.zoom) + self.screen_height / 2
        
        return (int(x_screen), int(y_screen))