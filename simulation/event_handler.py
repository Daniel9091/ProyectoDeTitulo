import pygame
from simulation.camera import Camera

class EventHandler:
    def __init__(self, simulation): 
        self.simulation = simulation
        self.camera = simulation.camera
    
    def handle_events(self):                                                                    # Maneja eventos de pygame y actualiza la cámara
        for event in pygame.event.get():
            if event.type == pygame.QUIT:                                                       # Salir del programa si se cierra la ventana
                return False
            elif event.type == pygame.KEYDOWN:                                                  # Manejar eventos de teclado    
                if event.key == pygame.K_i:                                                     # Alternar visualización de información (I)       
                    self.simulation.show_info = not self.simulation.show_info
                elif event.key == pygame.K_r:                                                   # Reiniciar simulación (R)
                    self.simulation.camera = Camera(self.simulation.camera.screen_width, 
                                                  self.simulation.camera.screen_height)
                
                # Pasar evento a la cámara y manejar comandos
                command = self.camera.handle_event(event)
                if command:
                    self.simulation.handle_command(command)
            
            elif event.type == pygame.MOUSEBUTTONDOWN:                                          # Pasar eventos de ratón a la cámara
                self.camera.handle_event(event)
        
        # Actualizar cámara según teclas presionadas
        keys = pygame.key.get_pressed()
        dt = 1/30  # Delta time aproximado para la cámara
        self.camera.update(keys, dt)
        
        return True