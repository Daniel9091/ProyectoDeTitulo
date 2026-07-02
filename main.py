import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pygame
from simulation_builder import inicial
from simulation.simulation import Simulation
from simulation.camera   import Camera
from simulation.renderer import Renderer
from config.constants    import FPS, SCREEN_WIDTH, SCREEN_HEIGHT

DT     = 1.0 / FPS
SPEEDS = [1, 2, 5, 10]

def main():
    print("Construyendo escenario...")
    brain, stations = inicial.build(seed=42)
    sim   = Simulation(brain, stations)
    train = brain._train

    pygame.init()
    pygame.display.set_caption("NSim — Sistema de Transporte Modular")
    screen   = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
    clock    = pygame.time.Clock()
    font_sm  = pygame.font.SysFont("monospace", 12)
    font_md  = pygame.font.SysFont("monospace", 15, bold=True)

    is_fullscreen = False
    windowed_size = (SCREEN_WIDTH, SCREEN_HEIGHT)

    z_belt   = train.start_pos.z
    camera   = Camera(SCREEN_WIDTH, SCREEN_HEIGHT,
                      pos=[1500.0, -600.0, 250.0], yaw=90.0, pitch=-20.0)
    renderer = Renderer(font_sm, font_md)   # ← ya no recibe camera

    speed_idx = 0
    paused    = False

    print("Corriendo — Esc para salir (o cerrar fullscreen). F11 = pantalla completa.")
    running = True
    while running:
        dt_real = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.VIDEORESIZE:

                if not is_fullscreen:
                    windowed_size = (event.w, event.h)
                    camera.on_resize(event.w, event.h)

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if is_fullscreen:
                        is_fullscreen = False
                        pygame.display.toggle_fullscreen()
                        screen = pygame.display.get_surface()
                        camera.on_resize(*screen.get_size())
                    else:
                        running = False
                elif event.key == pygame.K_F11:
                    is_fullscreen = not is_fullscreen
                    pygame.display.toggle_fullscreen()
                    screen = pygame.display.get_surface()
                    camera.on_resize(*screen.get_size())

                elif event.key == pygame.K_SPACE: paused    = not paused
                elif event.key == pygame.K_1:     speed_idx = 0
                elif event.key == pygame.K_2:     speed_idx = 1
                elif event.key == pygame.K_3:     speed_idx = 2
                elif event.key == pygame.K_4:     speed_idx = 3
            camera.handle_event(event)



        camera.update(dt_real)

        if not paused:
            for _ in range(SPEEDS[speed_idx]):
                sim.step(DT)

        renderer.render(
            screen, camera, train, brain._network, stations,
            sim.current_time, clock.get_fps(),
            SPEEDS[speed_idx], paused,
        )
        pygame.display.flip()

    pygame.quit()
    print(f"Parado en t={sim.current_time:.1f}s")

if __name__ == "__main__":
    main()