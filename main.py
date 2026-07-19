import sys, os
from setproctitle import setproctitle
sys.path.insert(0, os.path.dirname(__file__))

import json
import pygame
from pathlib import Path
from datetime import datetime
from simulation_builder import inicial
from simulation.simulation import Simulation
from simulation.inspector import Inspector
from simulation.camera   import Camera
from simulation.renderer import Renderer
from telemetry.recorder import Recorder, NullRecorder
from config.constants    import FPS, SCREEN_WIDTH, SCREEN_HEIGHT, TELEMETRY_ENABLED


DT     = 1.0 / FPS
SPEEDS = [1, 2, 5, 10]

def main():

    seed = 42
    scenario_name = "inicial"

    run_id  = f"{scenario_name}_seed{seed}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir = Path("runs") / run_id
    recorder = Recorder(run_dir, run_id) if TELEMETRY_ENABLED else NullRecorder()


    print(f"Construyendo escenario... (run_id={run_id})")
    brain, stations = inicial.build(seed=seed, recorder=recorder)
    recorder.run_started(t=0.0, config={"seed": seed, "scenario_name": scenario_name})

    # brain._process_reservations = lambda: None   # ← LÍNEA TEMPORAL: apaga reservas para forzar choques
    
    sim   = Simulation(brain, stations)
    train = brain._train

    try:
        pygame.init()
        pygame.display.set_caption("NSim — Sistema de Transporte Modular")
        screen   = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        clock    = pygame.time.Clock()
        font_sm  = pygame.font.SysFont("dejavusansmono,consolas,couriernew,monospace", 16)
        font_md  = pygame.font.SysFont("dejavusansmono,consolas,couriernew,monospace", 20, bold=True)


        is_fullscreen = False
        windowed_size = (SCREEN_WIDTH, SCREEN_HEIGHT)

        z_belt   = train.start_pos.z
        camera   = Camera(SCREEN_WIDTH, SCREEN_HEIGHT,
                        pos=[1500.0, -600.0, 250.0], yaw=90.0, pitch=-20.0)
        renderer = Renderer(font_sm, font_md)
        inspector = Inspector(font_sm, font_md)

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

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    inspector.handle_click(
                        event.pos, camera, train, brain._network, stations,
                        screen.get_width(),
                    )

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
            inspector.render(
                screen, camera, train, brain._network, stations,
                screen.get_width(),
            )

            pygame.display.flip()

        pygame.quit()
        print(f"Parado en t={sim.current_time:.1f}s")

    finally:
        summary = {"simulated_seconds": sim.current_time}
        brain.emit_vm_summaries(sim.current_time)
        recorder.run_ended(t=sim.current_time, summary=summary)
        recorder.close()

        if TELEMETRY_ENABLED:
            with open(run_dir / "summary.json", "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            index_path = Path("runs") / "index.jsonl"
            with open(index_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "run_id":        run_id,
                    "seed":          seed,
                    "scenario_name": scenario_name,
                    "events_path":   str(run_dir / "events.jsonl"),
                }) + "\n")

if __name__ == "__main__":
    setproctitle("nsim")
    main()