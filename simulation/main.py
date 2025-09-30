import pygame
import sys
from simulation.simulation import Simulation
from simulation.renderer import Renderer
from simulation.event_handler import EventHandler

def main():
    # Caracteristicas de la ventana
    pygame.init()
    width, height = 1200, 800
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Simulación Transporte Masivo Modular")
    
    # Inicializar simulación, renderizador y manejador de eventos
    simulation = Simulation(width, height)
    renderer = Renderer(screen, simulation.camera)
    event_handler = EventHandler(simulation)
    
    clock = pygame.time.Clock()                                     # Reloj para controlar FPS 
    fps = 30                                                        # FPS objetivo
    running = True                                                  # Bucle principal
    
    while running:                                                  # Bucle principal
        # Manejar eventos
        running = event_handler.handle_events()
        
        # Actualizar simulación
        dt = clock.get_time() / 1000.0
        simulation.update(dt)
        
        # Renderizar
        renderer.draw(simulation)
        
        # Actualizar pantalla
        pygame.display.flip()
        clock.tick(fps)
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":                                          # Ejuecución de la simulacion
    main()