import pygame

class EventHandler:
    def __init__(self, simulation): 
        self.simulation = simulation
        self.camera = simulation.camera
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_i:
                    self.simulation.show_info = not self.simulation.show_info
                elif event.key == pygame.K_r:  # Reiniciar cámara (R)
                    # Resetear la cámara
                    self.simulation.camera.reset()
                    # Actualizar la referencia local
                    self.camera = self.simulation.camera
                    print("Cámara resetada a posición inicial")
                
                # Pasar evento a la cámara y manejar comandos
                command = self.camera.handle_event(event)
                if command:
                    self.simulation.handle_command(command)
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.camera.handle_event(event)
        
        # Actualizar cámara según teclas presionadas
        keys = pygame.key.get_pressed()
        dt = 1/30  # Delta time aproximado para la cámara
        self.camera.update(keys, dt)
        
        return True